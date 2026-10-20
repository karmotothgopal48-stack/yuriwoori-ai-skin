"""Carts and checkout on the official store, priced by Shopify (Storefront API cartCreate, no token needed)."""

import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Cart
from app.schemas import CartQuoteRequest, CartQuoteResponse, CheckoutResponse
from app.services import shopify_cart
from app.services.live_catalogue import get_catalogue
from app.services.shopify_client import ShopifyError, create_cart

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/cart", response_model=CartQuoteResponse)
def cart_quote(payload: CartQuoteRequest):
    """Create a Shopify cart for these variants and return Shopify's own subtotal, discounts, total and the
    checkout URL of that cart (the checkout keeps the same lines and discounts). Only variants the store
    currently sells and has in stock are accepted."""
    catalogue = get_catalogue()
    sellable = {v["id"]: p for p in catalogue.products for v in p.variants if v["available"]}
    unknown = [l.variant_id for l in payload.lines if l.variant_id not in sellable]
    if unknown:
        raise HTTPException(status_code=400, detail="Some products in the cart are no longer available on yuriwoori.com. Please remove them and try again.")
    merged: dict[int, int] = {}
    for line in payload.lines:  # the same variant twice becomes one line
        merged[line.variant_id] = merged.get(line.variant_id, 0) + line.quantity
    try:
        quote = shopify_cart.quote([{"variant_id": v, "quantity": q} for v, q in merged.items()])
    except ShopifyError as exc:
        logger.error("Shopify cart was refused: %s", exc)
        raise HTTPException(status_code=400, detail="Shopify couldn't create this cart. Please check the products and try again.")
    except httpx.HTTPError as exc:
        logger.error("Shopify cart request failed: %s", exc)
        raise HTTPException(status_code=502, detail="Shopify couldn't be reached to price the cart. Please try again.")
    return CartQuoteResponse(**quote)


@router.post("/checkout/{cart_id}", response_model=CheckoutResponse)
def checkout(cart_id: uuid.UUID, db: Session = Depends(get_db)):
    """Checkout for a cart saved by the shopping agent (carts table)."""
    cart = db.get(Cart, cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    if not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Every line uses the product's CURRENT variant in the live store; products that are no longer sold
    # or are out of stock are reported, not added.
    catalogue = get_catalogue()
    lines = []
    unresolved = []
    for item in cart.items:
        live = catalogue.get(item.product.shopify_product_id)
        if live and live.available and live.variant_gid:
            lines.append({"merchandiseId": live.variant_gid, "quantity": item.quantity})
        else:
            unresolved.append(item.product.name)

    if not lines:
        raise HTTPException(
            status_code=400,
            detail=f"None of these products can be bought on yuriwoori.com right now: {', '.join(unresolved)}",
        )

    try:
        shopify_cart_data = create_cart(lines)
    except (httpx.HTTPError, ShopifyError) as exc:
        logger.error("Shopify cart creation failed: %s", exc)
        raise HTTPException(status_code=502, detail="Shopify checkout could not be created. Please try again.")
    cart.shopify_cart_id = shopify_cart_data["id"]
    db.commit()

    return CheckoutResponse(
        checkout_url=shopify_cart_data["checkoutUrl"],
        unresolved_products=unresolved,
    )
