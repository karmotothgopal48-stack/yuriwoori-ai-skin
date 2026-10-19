"""Protected admin reporting. Every route except /login needs an admin session token."""

import hmac
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ROLE_ADMIN, create_token, require_admin, verify_password
from app.db.session import get_db
from app.schemas import AdminLoginRequest, AdminLoginResponse
from app.services.report_excel import build_workbook
from app.services.reporting import IST, build_report

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest):
    if not settings.admin_email or not settings.admin_password_hash:
        raise HTTPException(status_code=503, detail="Admin login is not configured: run scripts/set_admin_password.py")
    email_ok = hmac.compare_digest(payload.email.strip().lower(), settings.admin_email.strip().lower())
    password_ok = verify_password(payload.password, settings.admin_password_hash)  # always evaluated (timing)
    if not (email_ok and password_ok):
        logger.warning("Failed admin login attempt")  # no email or IP in logs
        raise HTTPException(status_code=401, detail="Incorrect admin email or password.")
    token = create_token("admin", ROLE_ADMIN, timedelta(seconds=settings.jwt_expires_in))
    return AdminLoginResponse(token=token, expires_in=settings.jwt_expires_in)


@router.get("/summary")
def admin_summary(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    report = build_report(db)
    return {"summary": report["summary"], "product_engagement": report["product_engagement"]}


@router.get("/analyses")
def admin_analyses(limit: int = 200, offset: int = 0, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    rows = build_report(db)["analyses"]
    return {"total": len(rows), "items": rows[offset: offset + max(1, min(limit, 1000))]}


@router.get("/report.xlsx")
def admin_report_excel(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    content = build_workbook(build_report(db))
    name = f"yuriwoori-skin-analysis-report-{datetime.now(IST).strftime('%Y%m%d-%H%M')}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )


@router.get("/customer-sheet")
def admin_customer_sheet(limit: int = 200, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Google Sheets follow-up sync: whether it is on and configured (setting names only), counts by status, and the
    latest sync states by customer ID. No names, contacts or secrets: the sheet itself holds the customer details."""
    from app.db.models import CustomerSheetSync
    from app.services import customer_sheet, google_sheets
    rows = (db.query(CustomerSheetSync).order_by(CustomerSheetSync.updated_at.desc().nullslast(),
                                                 CustomerSheetSync.created_at.desc())
            .limit(max(1, min(limit, 1000))).all())
    when = lambda d: d.isoformat(timespec="seconds") + "Z" if d else None  # noqa: E731
    return {
        "enabled": settings.customer_sheet_sync_enabled,
        "problems": google_sheets.config_problems(),
        "worksheet": settings.google_sheets_worksheet_name,
        "eligibility": "consent to the current notice and a WhatsApp number verified with the one-time code",
        **customer_sheet.status_counts(db),
        "items": [{"customer_id": str(r.user_id), "status": r.status, "attempts": r.attempts, "last_error": r.last_error,
                   "last_synced_at": when(r.last_synced_at), "next_attempt_at": when(r.next_attempt_at),
                   "version": f"{r.synced_version}/{r.wanted_version}"} for r in rows],
    }
