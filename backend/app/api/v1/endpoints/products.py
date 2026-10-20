"""Products of the live official store (app/services/live_catalogue.py). Each has a stable UUID: its row in
the products table, which records live products so routines and carts can reference them."""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Product
from app.schemas import ProductResponse, ProductDetailResponse
from app.services.live_catalogue import StoreProduct, get_catalogue
from app.services.product_detail import parse_benefits
from app.services.product_records import ensure_product_rows

router = APIRouter()


def _fields(row: Product, p: StoreProduct) -> dict:
    return dict(
        id=row.id, name=p.name, price=p.price, currency=p.currency, image_url=p.image_url, category=p.category,
        routine_step=p.routine_step, description=p.description, product_url=p.product_url,
        handle=p.handle, available=p.available, variant_id=p.variant_id,
    )


@router.get("", response_model=list[ProductResponse])
def list_products(category: str | None = None, db: Session = Depends(get_db)):
    products = [p for p in get_catalogue().products if not category or p.category == category]
    rows = ensure_product_rows(db, products)
    db.commit()
    return [ProductResponse(**_fields(rows[p.handle], p)) for p in sorted(products, key=lambda p: p.name)]


@router.get("/{product_id}", response_model=ProductDetailResponse)
def get_product_detail(product_id: uuid.UUID, db: Session = Depends(get_db)):
    row = db.get(Product, product_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    product = get_catalogue().get(row.shopify_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="This product is no longer sold on yuriwoori.com")

    return ProductDetailResponse(
        **{k: v for k, v in _fields(row, product).items() if k not in ("handle", "available", "variant_id")},
        concern_tags=list(product.concern_tags),
        chips=list(product.chips),
        benefits=parse_benefits(product.benefits_raw),
        ingredients=sorted(product.ingredients),
    )
