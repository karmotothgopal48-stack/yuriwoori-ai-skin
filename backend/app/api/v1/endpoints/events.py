"""Engagement tracking for signed-up users: recommendations shown, product clicked.
Only products this scan actually offered can be recorded; URLs come from the catalogue."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import client_ip, current_user
from app.db.models import Scan, SkinProfile, User
from app.db.session import get_db
from app.schemas import EngagementEventRequest, EngagementEventResponse
from app.services.engagement import record_click, record_shown

router = APIRouter()


@router.post("", response_model=EngagementEventResponse)
def record_event(payload: EngagementEventRequest, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    scan = db.get(Scan, payload.scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.user_id != user.id:
        raise HTTPException(status_code=403, detail="This scan belongs to another user.")
    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan.id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Scan has no analyzed profile yet")

    ip = client_ip(request)
    if payload.event_type == "recommendations_shown":
        return EngagementEventResponse(recorded=record_shown(db, user.id, scan.id, profile, ip))

    if not payload.product_handle:
        raise HTTPException(status_code=422, detail="product_handle is required for product_clicked")
    try:
        return EngagementEventResponse(recorded=record_click(db, user.id, scan.id, profile, payload.product_handle, ip))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
