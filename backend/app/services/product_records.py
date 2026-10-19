"""
The products table as a RECORD of live catalogue products, never as a source for choosing them.

Saved routines, recommendations, carts and engagement events reference products by products.id, so every
product the app serves gets a row here, keyed by its Shopify handle (products.shopify_product_id) and kept
up to date from the live store (app/services/live_catalogue.py) each time it is served. Rows of products
the store no longer sells are kept (old records point at them) but marked inactive; nothing is deleted.
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Ingredient, Product, ProductIngredient, Routine, RoutineStep, TimeOfDay

logger = logging.getLogger(__name__)


def _row_values(p) -> dict:
    return dict(
        name=p.name, price=p.price, currency=p.currency, image_url=p.image_url, category=p.category,
        routine_step=p.routine_step, description=p.description, product_url=p.product_url,
        concern_tags=list(p.concern_tags), chips=list(p.chips), benefits_raw=p.benefits_raw,
        shopify_variant_id=p.variant_gid, active=True,
    )


def ensure_product_rows(db: Session, products) -> dict[str, Product]:
    """{handle: Product row} for these live products, created or refreshed from their live data (flushed, not committed)."""
    live = list({p.handle: p for p in products}.values())
    if not live:
        return {}
    rows = {r.shopify_product_id: r for r in
            db.query(Product).filter(Product.shopify_product_id.in_([p.handle for p in live])).all()}
    for p in live:
        values = _row_values(p)
        row = rows.get(p.handle)
        if row is None:
            rows[p.handle] = row = Product(shopify_product_id=p.handle, **values)
            db.add(row)
        else:
            for key, value in values.items():
                if getattr(row, key) != value:
                    setattr(row, key, value)
    db.flush()
    _sync_ingredients(db, [(rows[p.handle], p) for p in live if p.has_content])
    return rows


def _sync_ingredients(db: Session, pairs: list) -> None:
    """Each product's ingredient links follow its live INCI list (used by the routine compatibility check)."""
    pairs = [(row, p) for row, p in pairs if p.ingredients]  # no INCI on the page: leave existing links alone
    if not pairs:
        return
    names = {n for _, p in pairs for n in p.ingredients}
    ingredients = {i.name: i for i in db.query(Ingredient).filter(Ingredient.name.in_(names)).all()}
    for name in names - ingredients.keys():
        ingredients[name] = Ingredient(name=name, inci_name=name)
        db.add(ingredients[name])
    db.flush()

    product_ids = [row.id for row, _ in pairs]
    existing: dict = {}
    for link in db.query(ProductIngredient).filter(ProductIngredient.product_id.in_(product_ids)).all():
        existing.setdefault(link.product_id, {})[link.ingredient_id] = link
    for row, p in pairs:
        wanted = {ingredients[n].id for n in p.ingredients}
        have = existing.get(row.id, {})
        for ingredient_id in wanted - have.keys():
            db.add(ProductIngredient(product_id=row.id, ingredient_id=ingredient_id))
        for ingredient_id in have.keys() - wanted:  # no longer in the product's official INCI list
            db.delete(have[ingredient_id])
    db.flush()


def mark_unlisted_inactive(db: Session, catalogue) -> int:
    """Rows of products the live store no longer lists become inactive (kept for old records). Returns the count."""
    count = 0
    for row in db.query(Product).filter(Product.active == True).all():  # noqa: E712
        if catalogue.get(row.shopify_product_id) is None:
            row.active = False
            count += 1
    db.flush()
    return count


# ---------- saved routines ----------


def latest_routine(db: Session, profile_id) -> Routine | None:
    return (db.query(Routine).filter(Routine.skin_profile_id == profile_id)
            .order_by(Routine.created_at.desc()).first())


def _saved_signature(routine: Routine) -> list[tuple]:
    return sorted((s.time_of_day.value, s.step_order, str(s.product_id), s.reason) for s in routine.steps)


def _built_signature(built: dict, rows: dict[str, Product]) -> list[tuple]:
    return sorted((period, pick["step_order"], str(rows[pick["product"].handle].id), pick["reason"])
                  for period in ("AM", "PM") for pick in built[period])


def save_routine_if_changed(db: Session, profile, built: dict, rows: dict[str, Product]) -> Routine:
    """Record the routine just built from the live catalogue. A new Routine is added only when it differs
    from the latest saved one, so earlier versions stay as history but never replace the live result."""
    latest = latest_routine(db, profile.id)
    if latest is not None and _saved_signature(latest) == _built_signature(built, rows):
        return latest
    routine = Routine(user_id=profile.user_id, skin_profile_id=profile.id, created_at=datetime.utcnow())
    db.add(routine)
    db.flush()
    for period in ("AM", "PM"):
        for pick in built[period]:
            db.add(RoutineStep(routine_id=routine.id, time_of_day=TimeOfDay[period], step_order=pick["step_order"],
                               product_id=rows[pick["product"].handle].id, reason=pick["reason"],
                               concern_addressed=pick["step"]))
    db.flush()
    if latest is not None:
        logger.info("Routine for profile %s changed with the live catalogue; saved a new version", profile.id)
    return routine
