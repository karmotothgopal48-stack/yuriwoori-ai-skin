"""Skin-analysis reports (app/services/reports.py).

- The owner (signed-in user) creates and reads the report of their own scan, downloads its PDF, and can
  withdraw its link.
- Anyone with the secret link can read it until it expires or is withdrawn. The token travels in the
  X-Report-Token header (the link keeps it in the URL fragment), is compared by its SHA-256 only, and every
  invalid/expired/withdrawn token gets the same 404. Responses are not cached.
- The report is generated in memory for each response (reports.content_for) and is never stored.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.v1.endpoints.delivery import delivery_info, own_scan
from app.core.security import current_user
from app.db.models import Report, User
from app.db.session import get_db
from app.schemas import ReportCreateRequest, ReportStatusResponse, ReportViewResponse
from app.services import delivery, report_pdf, reports

router = APIRouter()
NO_STORE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex"}
NOT_FOUND = "This report link isn't valid or has expired."


def _content(db: Session, report: Report, not_found: bool = False) -> dict:
    try:
        return reports.content_for(db, report)
    except reports.ReportUnavailable as exc:
        if not_found:  # a link never says more than "not valid"
            raise HTTPException(status_code=404, detail=NOT_FOUND, headers=NO_STORE)
        raise HTTPException(status_code=422, detail=str(exc))


def status_response(db: Session, user: User, report: Report) -> ReportStatusResponse:
    return ReportStatusResponse(
        report_id=report.id, scan_id=report.scan_id, created_at=report.created_at, expires_at=report.expires_at,
        revoked=report.revoked_at is not None, report_consent=user.report_consent_at is not None,
        deliveries=[delivery_info(user, ch, delivery.delivery_row(db, report, ch)) for ch in delivery.CHANNELS],
    )


@router.post("", response_model=ReportStatusResponse)
def create_report(payload: ReportCreateRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Generate the report of the user's own analysed scan (once) and send it on every channel that is ready
    (configured, confirmed, consented). Channels that aren't ready stay pending, with the reason."""
    scan = own_scan(db, payload.scan_id, user)
    try:
        report = reports.get_or_create(db, user, scan)
    except reports.ReportUnavailable as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if report.revoked_at is None:
        delivery.deliver_all(db, user, report)
    db.commit()
    return status_response(db, user, report)


def _own_report(db: Session, scan_id: uuid.UUID, user: User) -> Report:
    own_scan(db, scan_id, user)
    report = db.query(Report).filter(Report.scan_id == scan_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="No report has been made for this scan yet.")
    return report


@router.get("/scan/{scan_id}", response_model=ReportStatusResponse)
def report_status(scan_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Delivery status of the report (for the results page to follow pending messages)."""
    report = _own_report(db, scan_id, user)
    response = status_response(db, user, report)
    db.commit()
    return response


@router.get("/scan/{scan_id}/pdf")
def own_report_pdf(scan_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    report = _own_report(db, scan_id, user)
    return Response(report_pdf.render(_content(db, report), reports.report_url(report)), media_type="application/pdf",
                    headers={**NO_STORE, "Content-Disposition": 'attachment; filename="YuriWoori-skin-report.pdf"'})


@router.post("/scan/{scan_id}/revoke", response_model=ReportStatusResponse)
def revoke_report(scan_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Withdraw the report link: it stops working for everyone, immediately."""
    report = _own_report(db, scan_id, user)
    if report.revoked_at is None:
        report.revoked_at = datetime.utcnow()
        db.commit()
    return status_response(db, user, report)


def _shared(db: Session, token: str | None) -> Report:
    report = reports.find_by_token(db, token or "")
    if report is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND, headers=NO_STORE)
    return report


@router.get("/shared", response_model=ReportViewResponse)
def shared_report(x_report_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    report = _shared(db, x_report_token)
    content = _content(db, report, not_found=True)
    report.last_viewed_at = datetime.utcnow()
    db.commit()
    body = ReportViewResponse(content=content, expires_at=report.expires_at)
    return Response(body.model_dump_json(), media_type="application/json", headers=NO_STORE)


@router.get("/shared/pdf")
def shared_report_pdf(x_report_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    report = _shared(db, x_report_token)
    return Response(report_pdf.render(_content(db, report, not_found=True), reports.report_url(report)), media_type="application/pdf",
                    headers={**NO_STORE, "Content-Disposition": 'attachment; filename="YuriWoori-skin-report.pdf"'})
