import uuid
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_db
from app.db.models import Scan, SkinProfile, Cart, CartItem
from app.schemas import ShoppingAgentRequest, ShoppingAgentResponse, AgentLineItem
from app.services.live_catalogue import get_catalogue
from app.services.product_records import ensure_product_rows
from app.services.shopping_agent import extract_budget, build_budget_routine

router = APIRouter()


@router.post("/build", response_model=ShoppingAgentResponse)
def build_agent_routine(payload: ShoppingAgentRequest, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    budget = extract_budget(payload.message)
    if budget is None:
        raise HTTPException(
            status_code=400,
            detail="Couldn't find a budget in that message — try something like '₹2000 budget'.",
        )

    profile = None
    if payload.scan_id:
        # a scan's skin profile is personal data: only its owner may use it
        user = current_user(authorization, db)
        scan = db.get(Scan, payload.scan_id)
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        if scan.user_id != user.id:
            raise HTTPException(status_code=403, detail="This scan belongs to another user.")
        profile = db.query(SkinProfile).filter(SkinProfile.scan_id == payload.scan_id).first()

    result = build_budget_routine(get_catalogue().products, budget, profile)
    rows = ensure_product_rows(db, [pick["product"] for pick in result["picks"]])

    cart = Cart(user_id=profile.user_id if profile else None)
    db.add(cart)
    db.flush()
    for pick in result["picks"]:
        db.add(CartItem(cart_id=cart.id, product_id=rows[pick["product"].handle].id, quantity=1))
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