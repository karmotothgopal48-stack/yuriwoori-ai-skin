"""Catalogue API backed by the live official store (app/services/live_catalogue.py): products, prices,
availability and variants are read from https://yuriwoori.com. No database is needed for browsing;
recommendations read the scan's skin profile only when a scan_id is given."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.models import Scan, SkinProfile
from app.db.session import get_db
from app.schemas import (
    CatalogueProductResponse,
    CatalogueRecommendation,
    CatalogueRecommendationsResponse,
    LiveCatalogueResponse,
)
from app.services.engagement import snapshot_recommendations
from app.services.product_detail import parse_benefits
from app.services.live_catalogue import StoreProduct, get_catalogue, store_url
from app.services.recommendation import METRIC_FIELDS, recommend
from app.services.skin_analysis import body_part_of, missing_measurements

router = APIRouter()


def _product_fields(p: StoreProduct) -> dict:
    return dict(
        handle=p.handle,
        name=p.name,
        price=p.price,
        image_url=p.image_url,
        category=p.category,
        routine_step=p.routine_step,
        description=p.description,
        product_url=p.product_url,
        concern_tags=list(p.concern_tags),
        chips=list(p.chips),
        ingredients=list(p.ingredients),
        key_benefit=p.key_benefit,
        how_to_use=p.how_to_use,
        benefits=parse_benefits(p.benefits_raw),
        product_id=p.product_id,
        variant_id=p.variant_id,
        available=p.available,
        compare_at_price=p.compare_at_price,
    )


@router.get("/products", response_model=list[CatalogueProductResponse])
def list_catalogue_products(
    step: str | None = Query(None, description="cleanse, tone, treat, moisturize, protect, mask, bundle"),
    concern: str | None = Query(None, description="concern tag, e.g. hydration, redness"),
    q: str | None = Query(None, description="case-insensitive text in the product name"),
    include_bundles: bool = False,
):
    products = get_catalogue().products
    if not include_bundles and step != "bundle":
        products = [p for p in products if p.routine_step != "bundle"]
    if step:
        products = [p for p in products if p.routine_step == step]
    if concern:
        products = [p for p in products if concern in p.concern_tags]
    if q:
        products = [p for p in products if q.lower() in p.name.lower()]
    return [CatalogueProductResponse(**_product_fields(p)) for p in products]


@router.get("/products/{handle}", response_model=CatalogueProductResponse)
def get_catalogue_product(handle: str):
    product = get_catalogue().get(handle)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in the catalogue")
    return CatalogueProductResponse(**_product_fields(product))


@router.get("/live", response_model=LiveCatalogueResponse)
def live_catalogue(handles: str = Query(..., description="Comma-separated Shopify product handles, e.g. rice-facial-deep-cleansing-foam")):
    """Current title, image, price, original price, discount, availability, URL and variants for these
    products, read from the official YuriWoori store. Handles not found in the store are left out."""
    wanted = list(dict.fromkeys(h.strip() for h in handles.split(",") if h.strip()))[:50]
    if not wanted:
        raise HTTPException(status_code=400, detail="Provide at least one product handle")
    catalogue = get_catalogue()
    products = [catalogue.by_handle[h].live_fields() for h in wanted if h in catalogue.by_handle]
    return LiveCatalogueResponse(store_url=store_url(), fetched_at=catalogue.fetched_at, stale=catalogue.stale, products=products)


@router.get("/recommendations", response_model=CatalogueRecommendationsResponse)
def catalogue_recommendations(
    scan_id: uuid.UUID | None = Query(None, description="Analyzed scan to recommend for"),
    hydration: float | None = Query(None, ge=0, le=100),
    oiliness: float | None = Query(None, ge=0, le=100),
    redness: float | None = Query(None, ge=0, le=100),
    pigmentation: float | None = Query(None, ge=0, le=100),
    blemish_index: float | None = Query(None, ge=0, le=100),
    pore_visibility: float | None = Query(None, ge=0, le=100),
    limit_per_step: int = Query(2, ge=1, le=10),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Recommend products from the live store catalogue for a skin analysis.

    Pass `scan_id` to use that scan's saved profile (only the scan's owner may), or pass the
    metrics directly (same 0-100 values `/scans/{id}/analyze` returns). `scan_id` wins if both are given.
    """
    body_part = "face"
    if scan_id:
        user = current_user(authorization, db)
        scan = db.get(Scan, scan_id)
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        if scan.user_id != user.id:
            raise HTTPException(status_code=403, detail="This scan belongs to another user.")
        profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
        if not profile:
            raise HTTPException(status_code=400, detail="Scan has no analyzed profile yet")
        body_part = body_part_of(scan.angles_captured)
        missing = missing_measurements(profile, body_part)
        if missing:
            raise HTTPException(status_code=422, detail=f"This analysis is incomplete (missing: {', '.join(missing)}). Please scan again.")
        metrics = {f: getattr(profile, f) for f in METRIC_FIELDS}
    else:
        metrics = dict(
            hydration=hydration, oiliness=oiliness, redness=redness, pigmentation=pigmentation,
            blemish_index=blemish_index, pore_visibility=pore_visibility,
        )
        if all(v is None for v in metrics.values()):
            raise HTTPException(status_code=400, detail="Provide a scan_id or at least one skin metric")

    catalogue = get_catalogue()
    concerns, ranked = recommend(metrics, catalogue.products, limit_per_step, body_part)
    if scan_id and profile.user_id and limit_per_step == 2:
        # what the app shows a signed-up user for this scan, kept as what was offered (first serve only)
        snapshot_recommendations(db, profile, ranked)
    return CatalogueRecommendationsResponse(
        scan_id=scan_id,
        analysis_status="concerns" if concerns else "balanced",
        active_concerns=concerns,
        recommendations=[
            CatalogueRecommendation(
                **_product_fields(item["product"]),
                rank=rank,
                score=item["score"],
                matched_concerns=item["matched_concerns"],
                match_reason=item["match_reason"],
            )
            for rank, item in enumerate(ranked, start=1)
        ],
        catalogue_fetched_at=catalogue.fetched_at,
        catalogue_stale=catalogue.stale,
    )
