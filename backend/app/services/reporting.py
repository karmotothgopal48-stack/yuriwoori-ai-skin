"""Admin analytics built only from real database rows (users, scans, skin_profiles,
recommendations, engagement_events). Purchases are reported as not confirmed: there is no
Shopify order integration, and a product click is never counted as a purchase."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import (EngagementEvent, EngagementEventType, Product, Recommendation, Scan, ScanStatus,
                           SkinProfile, User)
from app.services.recommendation import active_concerns

IST = timezone(timedelta(hours=5, minutes=30))
TZ_LABEL = "IST (UTC+05:30)"
PURCHASE_STATUS = "Not confirmed (no order integration)"
METRIC_FIELDS = ("hydration", "oiliness", "redness", "pigmentation", "blemish_index", "pore_visibility")
CONCERN_LABELS = {"redness": "Redness", "brightening": "Uneven tone", "uneven-tone": "Uneven tone", "blemish": "Blemishes",
                  "pore-visibility": "Pore visibility", "oiliness": "Oiliness", "hydration": "Low hydration"}


def to_ist(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc).astimezone(IST) if dt else None


def _pct(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def build_report(db: Session) -> dict:
    users = db.query(User).filter(User.consented_at.isnot(None)).order_by(User.created_at).all()
    user_ids = {u.id for u in users}
    scans = (db.query(Scan).filter(Scan.user_id.in_(user_ids)).order_by(Scan.created_at.desc()).all() if user_ids else [])
    profiles = {p.scan_id: p for p in db.query(SkinProfile).filter(SkinProfile.scan_id.in_([s.id for s in scans])).all()} if scans else {}
    recs = defaultdict(list)
    for r in (db.query(Recommendation).filter(Recommendation.skin_profile_id.in_([p.id for p in profiles.values()]))
              .order_by(Recommendation.rank).all() if profiles else []):
        recs[r.skin_profile_id].append(r)
    events = db.query(EngagementEvent).filter(EngagementEvent.user_id.in_(user_ids)).order_by(EngagementEvent.created_at).all() if user_ids else []
    products = {p.shopify_product_id: p for p in db.query(Product).all()}
    by_id = {u.id: u for u in users}

    shown_scans = {e.scan_id for e in events if e.event_type == EngagementEventType.recommendations_shown}
    clicks = [e for e in events if e.event_type == EngagementEventType.product_clicked]
    clicks_by_scan = defaultdict(list)
    for e in clicks:
        clicks_by_scan[e.scan_id].append(e)

    analyses = []
    for s in scans:
        p = profiles.get(s.id)
        if s.status != ScanStatus.analyzed or p is None:
            continue
        u = by_id[s.user_id]
        concerns = list(dict.fromkeys(CONCERN_LABELS.get(t, t) for t in active_concerns({f: getattr(p, f) for f in METRIC_FIELDS})))
        rec_names = [r.product.name for r in recs.get(p.id, [])]
        clicked = list(dict.fromkeys(products[e.product_handle].name if e.product_handle in products else e.product_handle
                                     for e in clicks_by_scan.get(s.id, [])))
        when = to_ist(s.created_at)
        analyses.append({
            "analysis_id": str(s.id), "user_name": u.name, "email": u.email,
            "date": when.strftime("%Y-%m-%d"), "time": when.strftime("%H:%M:%S"), "ip_address": s.client_ip,
            "skin_type": p.skin_type, "overall_score": p.overall_score,
            "detected_concerns": concerns, "recommended_products": rec_names,
            "recommendations_shown": s.id in shown_scans, "product_clicked": bool(clicked), "clicked_products": clicked,
            "purchase_status": PURCHASE_STATUS,
        })

    analysed_users = {a["email"] for a in analyses}
    rec_count = sum(len(a["recommended_products"]) for a in analyses)
    with_recs = sum(1 for a in analyses if a["recommended_products"])
    shown = sum(1 for a in analyses if a["recommendations_shown"])
    clicked_analyses = sum(1 for a in analyses if a["product_clicked"])

    rec_counter = Counter(n for a in analyses for n in a["recommended_products"])
    click_counter = Counter(products[e.product_handle].name if e.product_handle in products else e.product_handle for e in clicks)
    product_engagement = sorted(
        ({"product": n, "times_recommended": rec_counter.get(n, 0), "clicks": click_counter.get(n, 0),
          "product_url": next((p.product_url for p in products.values() if p.name == n), None)}
         for n in set(rec_counter) | set(click_counter)),
        key=lambda x: (-x["clicks"], -x["times_recommended"], x["product"]))

    summary = {
        "registered_users": len(users),
        "scans_started": len(scans),
        "completed_analyses": len(analyses),
        "unique_users_analyzed": len(analysed_users),
        "analyses_with_recommendations": with_recs,
        "products_recommended": rec_count,
        "analyses_recommendations_viewed": shown,
        "product_clicks": len(clicks),
        "analyses_with_product_click": clicked_analyses,
        "unique_products_clicked": len(click_counter),
        "confirmed_purchases": None,  # not available - see purchase_tracking
        "purchase_tracking": "Not available: no Shopify order integration is configured, so purchases cannot be confirmed.",
        "funnel": [
            {"stage": "Registered users", "count": len(users), "pct_of_previous": None},
            {"stage": "Users who completed an analysis", "count": len(analysed_users), "pct_of_previous": _pct(len(analysed_users), len(users))},
            {"stage": "Analyses with recommendations", "count": with_recs, "pct_of_previous": _pct(with_recs, len(analyses))},
            {"stage": "Analyses where recommendations were viewed", "count": shown, "pct_of_previous": _pct(shown, with_recs)},
            {"stage": "Analyses with a product click", "count": clicked_analyses, "pct_of_previous": _pct(clicked_analyses, shown)},
            {"stage": "Confirmed purchases", "count": None, "pct_of_previous": None},
        ],
        "timezone": TZ_LABEL,
        "generated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
    }

    user_rows = [{"name": u.name, "email": u.email, "registered_at": to_ist(u.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                  "consent_version": u.consent_version, "analyses": sum(1 for a in analyses if a["email"] == u.email)} for u in users]
    rec_rows = [{"analysis_id": a["analysis_id"], "email": a["email"], "rank": i, "product": n}
                for a in analyses for i, n in enumerate(a["recommended_products"], start=1)]
    click_rows = [{"analysis_id": str(e.scan_id), "email": by_id[e.user_id].email,
                   "product": products[e.product_handle].name if e.product_handle in products else e.product_handle,
                   "product_url": e.product_url, "clicked_at": to_ist(e.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                   "ip_address": e.client_ip} for e in clicks]
    return {"summary": summary, "analyses": analyses, "users": user_rows, "recommendations": rec_rows,
            "clicks": click_rows, "product_engagement": product_engagement}
