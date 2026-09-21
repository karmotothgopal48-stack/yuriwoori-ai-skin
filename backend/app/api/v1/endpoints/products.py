import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Product, ProductIngredient, Ingredient
from app.schemas import ProductResponse, ProductDetailResponse
from app.services.product_detail import parse_benefits

router = APIRouter()


@router.get("", response_model=list[ProductResponse])
def list_products(category: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Product).filter(Product.active == True)  # noqa: E712
    if category:
        query = query.filter(Product.category == category)
    return query.order_by(Product.name).all()


@router.get("/{product_id}", response_model=ProductDetailResponse)
def get_product_detail(product_id: uuid.UUID, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    ingredient_names = (
        db.query(Ingredient.name)
        .join(ProductIngredient, ProductIngredient.ingredient_id == Ingredient.id)
        .filter(ProductIngredient.product_id == product_id)
        .order_by(Ingredient.name)
        .all()
    )

    return ProductDetailResponse(
        id=product.id,
        name=product.name,
        price=product.price,
        currency=product.currency,
        image_url=product.image_url,
        category=product.category,
        routine_step=product.routine_step,
        description=product.description,
        product_url=product.product_url,
        concern_tags=product.concern_tags or [],
        chips=product.chips or [],
        benefits=parse_benefits(product.benefits_raw),
        ingredients=[name for (name,) in ingredient_names],
    )