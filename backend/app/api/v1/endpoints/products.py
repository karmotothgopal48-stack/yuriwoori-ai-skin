from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Product
from app.schemas import ProductResponse

router = APIRouter()


@router.get("", response_model=list[ProductResponse])
def list_products(category: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Product).filter(Product.active == True)  # noqa: E712
    if category:
        query = query.filter(Product.category == category)
    return query.order_by(Product.name).all()