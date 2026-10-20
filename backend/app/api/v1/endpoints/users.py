"""Signup for the skin analysis: name + WhatsApp number + email + accepted privacy notice -> user session token.
There is no password. A new email creates a user. An email that already has an account only opens it with proof:
the browser already holds that account's session, or the 6-digit code emailed to that address (the first request
answers code_required and sends it; the same form is sent again with the code). WhatsApp is not verified at
signup; results are only ever sent after the user confirms their mobile number with a code (endpoints/delivery.py)."""

import logging
import re
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ROLE_USER, create_token, current_user, decode_token
from app.db.models import User
from app.db.session import get_db
from app.schemas import SignupRequest, SignupResponse, UserPublic
from app.services import customer_sheet, delivery
from app.services.contact import mask_email, normalize_whatsapp

router = APIRouter()
logger = logging.getLogger(__name__)

# Bump when the privacy text in the frontend (screens/Signup.jsx, components/PrivacyPolicyModal.jsx) changes.
# 2026-10-19: the notice named a Microsoft 365 workbook (never accepted by any customer; replaced before use).
# 2026-10-19b: the notice names the team's Google Sheets follow-up spreadsheet.
# 2026-10-19c: explains WhatsApp verification, report delivery (generated, not stored), the sheet after verification
# and what is kept (customer_sheet.TRACKER_NOTICE_FROM).
CONSENT_VERSION = "2026-10-19c"


def _public(user: User) -> UserPublic:
    return UserPublic(id=user.id, name=user.name, email=user.email, whatsapp=user.whatsapp,
                      email_verified=user.email_verified_at is not None, whatsapp_verified=user.whatsapp_verified_at is not None,
                      report_consent=user.report_consent_at is not None)


def _session_user_id(authorization: str | None) -> uuid.UUID | None:
    """The user id of a valid session sent with the signup, else None (a missing/expired one is simply ignored)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        claims = decode_token(authorization.split(" ", 1)[1].strip())
        return uuid.UUID(claims["sub"]) if claims.get("role") == ROLE_USER else None
    except (HTTPException, ValueError, KeyError):
        return None


@router.post("/signup", response_model=SignupResponse)
def signup(payload: SignupRequest, background: BackgroundTasks, authorization: str | None = Header(default=None),
           db: Session = Depends(get_db)):
    if not payload.consent:
        raise HTTPException(status_code=400, detail="Please accept the privacy notice to continue.")
    name = re.sub(r"\s+", " ", payload.name).strip()
    if not name:
        raise HTTPException(status_code=422, detail="Please enter your name.")
    email = payload.email.strip().lower()
    whatsapp = normalize_whatsapp(payload.whatsapp)
    if not whatsapp:
        raise HTTPException(status_code=422, detail="Please enter a valid WhatsApp number, with the country code if it isn't an Indian number.")

    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user is None:
        user = User(email=email)
        db.add(user)
    elif _session_user_id(authorization) != user.id:
        # an existing account: knowing its email isn't enough to open it
        try:
            if not payload.code:
                delivery.start_login(db, user)
                return SignupResponse(code_required=True, sent_to=mask_email(user.email))
            delivery.confirm_login(db, user, payload.code)
        except delivery.DeliveryRefused as exc:
            raise HTTPException(status_code=exc.status, detail=str(exc))
    user.name = name
    if user.whatsapp != whatsapp:  # a new number must be confirmed again before anything is sent to it
        user.whatsapp = whatsapp
        user.whatsapp_verified_at = None
    user.consented_at = datetime.utcnow()
    user.consent_version = CONSENT_VERSION
    # sending the report is a separate, explicit choice (and can be withdrawn by signing up without it)
    user.report_consent_at = (user.report_consent_at or datetime.utcnow()) if payload.report_consent else None
    # signup and sign-in alike: queued (once the WhatsApp number is verified), written to the Google Sheet after the response
    customer_sheet.mark_changed(db, user)
    db.commit()
    db.refresh(user)
    logger.info("User signed up / signed in: %s", user.id)  # id only - no name or email in logs

    background.add_task(customer_sheet.run_in_background)
    token = create_token(str(user.id), ROLE_USER, timedelta(days=settings.user_token_days))
    return SignupResponse(token=token, user=_public(user))


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(current_user)):
    return _public(user)
