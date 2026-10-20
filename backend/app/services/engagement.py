"""Records what each signed-up user was recommended, saw and clicked.

- The ranked product list served for a scan is snapshotted once into the existing
  `recommendations` table: what the user was actually offered (a click is accepted only for one of these).
- `engagement_events` stores "recommendations shown" and "product clicked" rows.
Product handles and URLs always come from the live store catalogue (as recorded in the products table
when they were served), never from the browser.
Purchases are not recorded: a click is not a purchase and there is no order integration.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import EngagementEvent, EngagementEventType, Product, Recommendation, Routine, SkinProfile
from app.services.product_records import ensure_product_rows

logger = logging.getLogger(__name__)


def snapshot_recommendations(db: Session, profile: SkinProfile, ranked: list[dict]) -> None:
    """Store the served ranking (live catalogue products) for this profile once, the first time it is served:
    a historical record for reports. It is never read back to decide what to show."""
    if db.query(Recommendation).filter(Recommendation.skin_profile_id == profile.id).first():
        return
    rows = ensure_product_rows(db, [item["product"] for item in ranked])
    for rank, item in enumerate(ranked, start=1):
        db.add(Recommendation(user_id=profile.user_id, skin_profile_id=profile.id, product_id=rows[item["product"].handle].id,
                              rank=rank, match_reason=item["match_reason"]))
    db.commit()


def recommended_rows(db: Session, profile_id: uuid.UUID) -> list[Recommendation]:
    return (db.query(Recommendation).filter(Recommendation.skin_profile_id == profile_id)
            .order_by(Recommendation.rank).all())


def record_shown(db: Session, user_id: uuid.UUID, scan_id: uuid.UUID, profile: SkinProfile, ip: str | None) -> int:
    """One row per recommended product the user was shown; recorded once per scan. Concurrent requests
    are safe: the partial unique index uq_engagement_shown_once makes repeats a no-op (ON CONFLICT DO NOTHING)."""
    recorded = 0
    for r in recommended_rows(db, profile.id):
        stmt = pg_insert(EngagementEvent).values(
            id=uuid.uuid4(), event_type=EngagementEventType.recommendations_shown, user_id=user_id, scan_id=scan_id,
            product_handle=r.product.shopify_product_id, product_url=r.product.product_url, rank=r.rank,
            client_ip=ip, created_at=datetime.utcnow(),
        ).on_conflict_do_nothing(index_elements=["scan_id", "product_handle"],
                                 index_where=text("event_type = 'recommendations_shown'"))
        recorded += db.execute(stmt).rowcount
    db.commit()
    return recorded


def scan_product_handles(db: Session, profile: SkinProfile) -> dict[str, int | None]:
    """Handles this scan offered the user: recommended products (with rank) and the products of every
    routine version served for it (a routine is re-saved when the live catalogue changes it)."""
    handles: dict[str, int | None] = {r.product.shopify_product_id: r.rank for r in recommended_rows(db, profile.id)}
    for routine in db.query(Routine).filter(Routine.skin_profile_id == profile.id).all():
        for step in routine.steps:
            handles.setdefault(step.product.shopify_product_id, None)
    return handles


def record_click(db: Session, user_id: uuid.UUID, scan_id: uuid.UUID, profile: SkinProfile, handle: str, ip: str | None) -> int:
    offered = scan_product_handles(db, profile)
    if handle not in offered:
        raise ValueError("That product was not recommended for this scan.")
    product = db.query(Product).filter(Product.shopify_product_id == handle).first()  # recorded when served
    if product is None or not product.product_url:
        raise ValueError("That product is not in the YuriWoori catalogue.")
    db.add(EngagementEvent(event_type=EngagementEventType.product_clicked, user_id=user_id, scan_id=scan_id,
                           product_handle=handle, product_url=product.product_url, rank=offered[handle], client_ip=ip))
    db.commit()
    return 1
