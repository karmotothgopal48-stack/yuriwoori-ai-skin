import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Cart
from app.schemas import CheckoutResponse
from app.services.shopify_client import create_cart

router = APIRouter()


@router.post("/checkout/{cart_id}", response_model=CheckoutResponse)
def checkout(cart_id: uuid.UUID, db: Session = Depends(get_db)):
    cart = db.get(Cart, cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    if not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    lines = []
    unresolved = []
    for item in cart.items:
        if item.product.shopify_variant_id:
            lines.append({"merchandiseId": item.product.shopify_variant_id, "quantity": item.quantity})
        else:
            unresolved.append(item.product.name)

    if not lines:
        raise HTTPException(
            status_code=400,
            detail=f"None of these products have a resolved Shopify variant yet: {', '.join(unresolved)}",
        )

    shopify_cart = create_cart(lines)
    cart.shopify_cart_id = shopify_cart["id"]
    db.commit()

    return CheckoutResponse(
        checkout_url=shopify_cart["checkoutUrl"],
        unresolved_products=unresolved,
    )