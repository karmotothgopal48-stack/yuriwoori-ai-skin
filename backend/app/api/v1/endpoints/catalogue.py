"""Catalogue API backed directly by data/products_export.csv (no database needed for
browsing; recommendations read the scan's skin profile only when a scan_id is given)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import SkinProfile
from app.db.session import get_db
from app.schemas import (
    CatalogueProductResponse,
    CatalogueRecommendation,
    CatalogueRecommendationsResponse,
)
from app.services.catalogue_csv import CsvProduct, get_product, load_catalogue, recommend

router = APIRouter()

METRIC_FIELDS = ("hydration", "oiliness", "texture", "redness", "pigmentation", "blemish_index", "pore_visibility")


def _product_fields(p: CsvProduct) -> dict:
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
    )


@router.get("/products", response_model=list[CatalogueProductResponse])
def list_catalogue_products(
    step: str | None = Query(None, description="cleanse, tone, treat, moisturize, protect, mask, bundle"),
    concern: str | None = Query(None, description="concern tag, e.g. hydration, redness"),
    q: str | None = Query(None, description="case-insensitive text in the product name"),
    include_bundles: bool = False,
):
    products = load_catalogue()
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
    product = get_product(handle)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in the catalogue")
    return CatalogueProductResponse(**_product_fields(product))


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
    db: Session = Depends(get_db),
):
    """Recommend products from the CSV catalogue for a skin analysis.

    Pass `scan_id` to use that scan's saved profile, or pass the metrics directly
    (same 0-100 values `/scans/{id}/analyze` returns). `scan_id` wins if both are given.
    """
    if scan_id:
        profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
        if not profile:
            raise HTTPException(status_code=400, detail="Scan has no analyzed profile yet")
        metrics = {f: getattr(profile, f) for f in METRIC_FIELDS}
    else:
        metrics = dict(
            hydration=hydration, oiliness=oiliness, redness=redness, pigmentation=pigmentation,
            blemish_index=blemish_index, pore_visibility=pore_visibility,
        )
        if all(v is None for v in metrics.values()):
            raise HTTPException(status_code=400, detail="Provide a scan_id or at least one skin metric")

    concerns, ranked = recommend(metrics, limit_per_step)
    return CatalogueRecommendationsResponse(
        scan_id=scan_id,
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
    )
