"""Sending a customer their own skin-analysis report by email or WhatsApp (app/services/delivery.py), and the
WhatsApp status webhook. Only the signed-in user's own scans, only to their own contact, only after they
confirmed that contact with a one-time code and agreed to have the report sent."""

import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import current_user
from app.db.models import Report, ResultDelivery, Scan, User
from app.db.session import get_db
from app.schemas import (DeliveryChannelRequest, DeliveryChannelStatus, DeliveryConfirmRequest, DeliveryInfo,
                         DeliveryStatusResponse)
from app.services import customer_sheet, delivery, reports

router = APIRouter()
logger = logging.getLogger(__name__)


def _refused(exc):
    return HTTPException(status_code=exc.status, detail=str(exc))


def delivery_info(user: User, channel: str, row: ResultDelivery | None) -> DeliveryInfo:
    reason = delivery.blocker(user, channel, row)
    status = row.status if row else "pending"
    return DeliveryInfo(
        channel=channel, status=status, configured=delivery.configured(channel), verified=delivery.verified(user, channel),
        destination=delivery.masked(channel, delivery.destination(user, channel)),
        reason=reason if status in ("pending", "failed") else None,
        attempts=row.attempts if row else 0, sent_at=row.sent_at if row else None, updated_at=row.updated_at if row else None,
        can_retry=status in ("pending", "failed") and reason is None,
    )


def own_scan(db: Session, scan_id: uuid.UUID, user: User) -> Scan:
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.user_id != user.id:
        raise HTTPException(status_code=403, detail="This scan belongs to another user.")
    return scan


@router.get("/status", response_model=DeliveryStatusResponse)
def delivery_status(user: User = Depends(current_user)):
    """Which channels can be used, and whether the user's own contact for each is confirmed (masked)."""
    return DeliveryStatusResponse(**{
        channel: DeliveryChannelStatus(available=delivery.configured(channel) and delivery.test_mode_allows(channel, delivery.destination(user, channel)), verified=delivery.verified(user, channel),
                                       destination=delivery.masked(channel, delivery.destination(user, channel)))
        for channel in delivery.CHANNELS
    }, report_consent=user.report_consent_at is not None)


@router.post("/verify/start")
def verify_start(payload: DeliveryChannelRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        delivery.start_verification(db, user, payload.channel)
    except delivery.DeliveryRefused as exc:
        raise _refused(exc)
    return {"sent_to": delivery.masked(payload.channel, delivery.destination(user, payload.channel))}


@router.post("/verify/confirm")
def verify_confirm(payload: DeliveryConfirmRequest, background: BackgroundTasks, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    try:
        delivery.confirm_verification(db, user, payload.channel, payload.code)
    except delivery.DeliveryRefused as exc:
        raise _refused(exc)
    customer_sheet.mark_changed(db, user)  # the workbook shows the new verification status
    db.commit()
    background.add_task(customer_sheet.run_in_background)
    # reports waiting only for this confirmation go out now (each at most once). Confirming the mobile number
    # releases every channel, because mobile verification is what every report waits for.
    channels = delivery.CHANNELS if payload.channel == "whatsapp" else (payload.channel,)
    sent = []
    for report in db.query(Report).filter(Report.user_id == user.id, Report.revoked_at.is_(None)).all():
        for channel in channels:
            row = delivery.delivery_row(db, report, channel)
            if row.status == "pending":
                sent.append(delivery_info(user, channel, delivery.deliver(db, user, report, channel)))
    return {"verified": True, "deliveries": [d.model_dump(mode="json") for d in sent]}


@router.post("/scans/{scan_id}/send", response_model=DeliveryInfo)
def send_report(scan_id: uuid.UUID, payload: DeliveryChannelRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Send (or safely retry) this scan's report on one channel. Asking for it is the user's consent to have
    the report sent; a report the provider already has is not sent again."""
    scan = own_scan(db, scan_id, user)
    if user.report_consent_at is None:
        user.report_consent_at = datetime.utcnow()
        db.commit()
    try:
        report = reports.get_or_create(db, user, scan)
    except reports.ReportUnavailable as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if report.revoked_at is not None:
        raise HTTPException(status_code=410, detail="This report was withdrawn.")
    return delivery_info(user, payload.channel, delivery.deliver(db, user, report, payload.channel))


# ---------- WhatsApp Cloud API status webhook ----------


@router.get("/whatsapp/webhook", response_class=PlainTextResponse)
def whatsapp_webhook_verify(mode: str = Query(alias="hub.mode", default=""), token: str = Query(alias="hub.verify_token", default=""),
                            challenge: str = Query(alias="hub.challenge", default="")):
    """Meta's subscription check: echo the challenge only for our verify token."""
    if not settings.whatsapp_webhook_verify_token or mode != "subscribe" or token != settings.whatsapp_webhook_verify_token:
        raise HTTPException(status_code=403, detail="Forbidden")
    return challenge


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """Message status callbacks (sent / delivered / read / failed), and messages customers send to the business
    number (forwarded to the team by email). Only requests signed with the Meta app secret are accepted."""
    raw = await request.body()
    if not delivery.valid_signature(raw, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=403, detail="Invalid signature")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    updated = delivery.apply_whatsapp_statuses(db, payload)
    try:
        forwarded = delivery.forward_whatsapp_replies(db, payload)
    except delivery.ReplyForwardingFailed:
        raise HTTPException(status_code=503, detail="Could not forward the message; please retry")  # Meta retries
    return {"updated": updated, "forwarded": forwarded}
