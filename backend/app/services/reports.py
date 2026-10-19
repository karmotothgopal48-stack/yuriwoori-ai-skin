"""
A customer's skin-analysis report: built ONLY from their saved analysis (skin_profiles), the same
recommendation/routine rules as the app, the live Shopify catalogue, and Shopify's own pricing of the routine
(cartCreate: subtotal, the discounts Shopify applies, total). Nothing is estimated: a part that can't be
obtained is left out and marked unavailable. The report contains no face image.

NOTHING OF THE REPORT IS STORED: the content is generated in memory (content_for) each time the report is sent,
its PDF downloaded or its link opened, then discarded. Only the record that a report exists (scan, customer, link
token hash, expiry) and its delivery status are kept. Reports made before this keep their stored content as it
is (never read or changed; enforced in db/models.py). Prices in it are as of `generated_at` (that moment); the
checkout always prices the cart again.

Report links: the token is HMAC(JWT_SECRET, report id) — reproducible by the server (so retries and the
email/WhatsApp messages carry the same link) but unguessable, and only its SHA-256 is stored.
"""

import base64
import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Report, Scan, SkinProfile, User
from app.services import shopify_cart
from app.services.benchmark import BENCHMARK_VERSION, benchmark_for
from app.services.live_catalogue import get_catalogue
from app.services.live_catalogue import usage_guidance
from app.services.recommendation import ROUTINE_ORDER, concern_details, profile_metrics, recommend
from app.services.routine_builder import build_maintenance_routine, build_routine
from app.services.shopify_client import ShopifyError
from app.services.skin_analysis import body_part_of, missing_measurements

logger = logging.getLogger(__name__)

REPORT_VERSION = 1
DISCLAIMER = "This analysis is for skincare guidance and is not a medical diagnosis."

# The app's own metric definitions and explanations (frontend data/mock.js METRIC_INFO): what each value
# actually measures. No other interpretation is given.
METRICS = [
    ("hydration", "Hydration", True, "An estimate from how smooth the skin looks and how much shine it has — not a direct moisture reading."),
    ("oiliness", "Oiliness", False, "How much of the face shows bright, low-colour highlights (shine)."),
    ("texture", "Texture", True, "How smooth the skin area looks, from the amount of fine detail in the photo."),
    ("redness", "Redness", False, "The average red tone of the skin-coloured pixels in the measured skin area."),
    ("pigmentation", "Uneven tone", False, "How much the brightness of your skin varies across the measured skin area."),
    ("pore_visibility", "Pore visibility", False, "The amount of fine detail in the centre of the face (nose and inner cheeks)."),
    ("blemish_index", "Blemishes", False, "How many small reddish spots appear on the skin."),
]
METRIC_TAGS = {"hydration": ["hydration"], "oiliness": ["oiliness"], "redness": ["redness"], "pigmentation": ["brightening", "uneven-tone"],
               "pore_visibility": ["pore-visibility"], "blemish_index": ["blemish"], "texture": []}
DAILY_STEPS = {"cleanse", "tone", "treat", "moisturize", "protect"}


class ReportUnavailable(ValueError):
    """The report can't be made (no saved analysis, incomplete analysis)."""


# ---------- links ----------


def link_token(report_id) -> str:
    digest = hmac.new(settings.jwt_secret.encode(), f"report-link:{report_id}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def report_url(report: Report) -> str:
    """The secure link. The token is in the URL fragment (#), which browsers never send to servers or put in
    Referer headers; the report page passes it to the API in a header."""
    return f"{settings.frontend_public_url.rstrip('/')}/report#t={link_token(report.id)}"


def find_by_token(db: Session, token: str) -> Report | None:
    """The report for a link token, if the link is still valid (not expired, not revoked)."""
    if not token or len(token) > 100:
        return None
    report = db.query(Report).filter(Report.token_hash == token_hash(token)).first()
    if report is None or report.revoked_at is not None or report.expires_at < datetime.utcnow():
        return None
    return report


# ---------- content ----------


def _product(p) -> dict:
    usage = usage_guidance(p.how_to_use, p.body_html)
    return {
        "handle": p.handle, "name": p.name, "url": p.product_url, "image_url": p.image_url,
        "product_id": p.product_id, "variant_id": p.variant_id, "price": p.price, "compare_at_price": p.compare_at_price,
        "discount_percent": p.discount_percent, "available": p.available, "routine_step": p.routine_step,
        "how_to_use": p.how_to_use, "key_benefit": p.key_benefit, "usage_frequency": (usage or {}).get("frequency"),
        "usage_quote": (usage or {}).get("quote"),
    }


def _concerns(details: dict) -> list[dict]:
    """[{phrase, tags}] most severe first; tags that share a phrase (brightening / uneven-tone) are listed once."""
    by_phrase: dict[str, dict] = {}
    for tag, (phrase, severity) in sorted(details.items(), key=lambda kv: -kv[1][1]):
        by_phrase.setdefault(phrase, {"phrase": phrase, "tags": []})["tags"].append(tag)
    return list(by_phrase.values())


def build_content(user: User, scan: Scan, profile: SkinProfile) -> dict:
    body_part = body_part_of(scan.angles_captured)
    if missing_measurements(profile, body_part):
        raise ReportUnavailable("This analysis is incomplete, so no report can be made from it.")
    metrics = profile_metrics(profile)
    details = concern_details(metrics)
    benchmark = benchmark_for(body_part)
    catalogue = get_catalogue()

    metric_rows = []
    for key, label, higher_is_better, measures in METRICS:
        value = metrics.get(key)
        if value is None:
            continue  # not measured for this scan type (e.g. oiliness on a hand)
        flagged = [t for t in METRIC_TAGS[key] if t in details]
        metric_rows.append({
            "key": key, "label": label, "value": round(value), "higher_is_better": higher_is_better, "measures": measures,
            "benchmark": round(benchmark[key]) if key in benchmark else None,
            "concern": details[flagged[0]][0] if flagged else None,
        })

    if details:
        built = build_routine(profile, catalogue.products, body_part)
        _, ranked = recommend(metrics, catalogue.products, 2, body_part)
    else:
        built, ranked = build_maintenance_routine(catalogue.products, body_part), []

    products: dict[str, dict] = {}
    routine = {}
    for period in ("AM", "PM"):
        routine[period] = []
        for pick in built[period]:
            products.setdefault(pick["product"].handle, _product(pick["product"]))
            routine[period].append({"step_order": pick["step_order"], "step": pick["step"], "reason": pick["reason"],
                                    "handle": pick["product"].handle})
    in_routine = set(products)
    extras = []
    for item in ranked:  # recommended products outside the daily steps (masks, eye patches...), as on the routine page
        p = item["product"]
        if p.routine_step in DAILY_STEPS or p.handle in in_routine or any(e["handle"] == p.handle for e in extras):
            continue
        products.setdefault(p.handle, _product(p))
        extras.append({"handle": p.handle, "reason": item["match_reason"], "matched_concerns": item["matched_concerns"]})

    routine_variants = list(dict.fromkeys(products[s["handle"]]["variant_id"] for period in ("AM", "PM") for s in routine[period]))
    pricing = None
    if routine_variants:
        try:
            quote = shopify_cart.quote([{"variant_id": v, "quantity": 1} for v in routine_variants])
            pricing = {k: quote[k] for k in ("currency", "subtotal", "discounts", "total")} | {
                "quoted_at": datetime.utcnow().isoformat(timespec="seconds") + "Z", "variant_ids": routine_variants}
        except (ShopifyError, httpx.HTTPError) as exc:
            logger.warning("Shopify couldn't price the routine for scan %s: %s", scan.id, exc)  # left out, never estimated

    return {
        "version": REPORT_VERSION,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "analysis_date": (profile.created_at or scan.created_at).isoformat(timespec="seconds") + "Z",
        "customer_name": user.name,
        "body_part": body_part,
        "skin_type": (profile.skin_type or "").capitalize() or None,
        "overall_score": round(profile.overall_score) if profile.overall_score is not None else None,
        "benchmark_note": f"Typical values are fixed internal YuriWoori benchmarks ({BENCHMARK_VERSION}), for comparison only — not medical or population norms." if benchmark else None,
        "metrics": metric_rows,
        "analysis_status": "concerns" if details else "balanced",
        "concerns": _concerns(details),
        "routine": routine,
        "extras": extras,
        "products": products,
        "pricing": pricing,
        "catalogue_fetched_at": catalogue.fetched_at,
        "step_order": ROUTINE_ORDER,
        "disclaimer": DISCLAIMER,
    }


def _profile(db: Session, scan: Scan) -> SkinProfile:
    """The scan's saved, complete analysis, or ReportUnavailable."""
    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan.id).first()
    if profile is None:
        raise ReportUnavailable("This scan has no saved analysis yet.")
    if missing_measurements(profile, body_part_of(scan.angles_captured)):
        raise ReportUnavailable("This analysis is incomplete, so no report can be made from it.")
    return profile


def content_for(db: Session, report: Report) -> dict:
    """The report, generated now in memory from its own scan's saved analysis and its owner's details (never stored)."""
    scan = db.get(Scan, report.scan_id)
    user = db.get(User, report.user_id)
    if scan is None or user is None or scan.user_id != report.user_id:
        raise ReportUnavailable("This report's analysis is no longer available.")
    return build_content(user, scan, _profile(db, scan))


def get_or_create(db: Session, user: User, scan: Scan) -> Report:
    """The scan's report record, made once (one per scan; two requests at the same time get the same one).
    Only the record is saved: the content is generated whenever it is needed (content_for)."""
    report = db.query(Report).filter(Report.scan_id == scan.id).first()
    if report is not None:
        return report
    _profile(db, scan)  # only a complete, saved analysis gets a report
    now = datetime.utcnow()
    report_id = uuid.uuid4()  # its id (and so its token) before the insert: no shared placeholder token
    try:
        with db.begin_nested():
            report = Report(id=report_id, scan_id=scan.id, user_id=user.id, content=None,
                            token_hash=token_hash(link_token(report_id)),
                            created_at=now, expires_at=now + timedelta(days=settings.report_link_days))
            db.add(report)
    except IntegrityError:  # the other request made this scan's report first
        return db.query(Report).filter(Report.scan_id == scan.id).one()
    db.commit()
    logger.info("Report %s created for scan %s", report.id, scan.id)
    return report
