import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import SkinProfile, Cart, CartItem
from app.schemas import ShoppingAgentRequest, ShoppingAgentResponse, AgentLineItem
from app.services.shopping_agent import extract_budget, build_budget_routine

router = APIRouter()


@router.post("/build", response_model=ShoppingAgentResponse)
def build_agent_routine(payload: ShoppingAgentRequest, db: Session = Depends(get_db)):
    budget = extract_budget(payload.message)
    if budget is None:
        raise HTTPException(
            status_code=400,
            detail="Couldn't find a budget in that message — try something like '₹2000 budget'.",
        )

    profile = None
    if payload.scan_id:
        profile = db.query(SkinProfile).filter(SkinProfile.scan_id == payload.scan_id).first()

    result = build_budget_routine(db, budget, profile)

    cart = Cart(user_id=profile.user_id if profile else None)
    db.add(cart)
    db.flush()
    for pick in result["picks"]:
        db.add(CartItem(cart_id=cart.id, product_id=pick["product"].id, quantity=1))
    db.commit()

    tags = []
    if result["fits_budget"]:
        tags.append("Fits your budget")
    if result["matches_profile"]:
        tags.append("Matches your profile")

    return ShoppingAgentResponse(
        cart_id=cart.id,
        items=[
            AgentLineItem(name=p["product"].name, step=p["step"], price=p["product"].price)
            for p in result["picks"]
        ],
        total=result["total"],
        budget=result["budget"],
        tags=tags,
    )