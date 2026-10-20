"""
Sending a customer their skin-analysis report (services/reports.py) by email and WhatsApp.

Rules:
- A channel is only used when it is configured (settings: SMTP_* for email, WHATSAPP_* for WhatsApp).
- Reports only ever go to the report owner's OWN email / WhatsApp number as it was when the report was made
  (result_deliveries.destination), only with their consent to have it sent (users.report_consent_at), and only
  after they verified their mobile (WhatsApp) number with a one-time code (contact_verifications; only an HMAC of
  the code is stored). The email address needs no code unless EMAIL_REPORT_REQUIRES_EMAIL_VERIFICATION is set.
- One delivery row per report and channel (result_deliveries); retries update it, so nothing is sent twice:
    pending -> sending -> sent (email: the SMTP server accepted it)
                       -> accepted (WhatsApp Cloud API accepted it) -> sent / delivered / failed (WhatsApp webhook)
                       -> failed (safe to retry)
  A message is never marked sent without the provider saying so.
- Email: a short summary + the PDF attached + the secure link. WhatsApp: an approved template with a short
  summary and the secure link (+ the PDF as a document header when the template was approved with one).
- The report content and PDF are generated in memory for each send (reports.content_for) and never stored. A PDF
  uploaded to WhatsApp's media store is deleted there once WhatsApp reports the message delivered, read or failed
  (webhook), right away if the message couldn't be sent, and otherwise by purge_whatsapp_media after a while.
- After an analysis, report_after_analysis makes the report and sends it from the backend (no browser needed).
- Logs carry masked contacts only, never codes, tokens, links or report content.
"""

import hashlib
import hmac
import logging
import re
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import make_msgid
from html import escape

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import ContactVerification, Report, ResultDelivery, User
from app.services import report_pdf, reports
from app.services.contact import mask_email, mask_phone, normalize_whatsapp
from app.services.live_catalogue import LiveCatalogueUnavailable

logger = logging.getLogger(__name__)

CHANNELS = ("email", "whatsapp")
CODE_TTL = timedelta(minutes=10)
CODE_RESEND_AFTER = timedelta(seconds=60)
CODES_PER_HOUR = 5
MAX_ATTEMPTS = 5
SENDING_TIMEOUT = timedelta(minutes=5)  # a "sending" row older than this (e.g. after a crash) may be retried
DONE = {"sent", "delivered", "accepted"}  # provider has the message: never send again


class DeliveryError(RuntimeError):
    """The provider refused or couldn't be reached. The message is safe to log (no secrets, no content)."""


class DeliveryRefused(ValueError):
    """The request can't be done (not configured, not verified, too many codes, wrong code, ...).
    `status` is the HTTP status for the API; the message is shown to the user."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------- configuration and readiness ----------


def configured(channel: str) -> bool:
    if channel == "email":
        return bool(settings.smtp_host and settings.smtp_from)
    if channel == "whatsapp":
        return bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id
                    and settings.whatsapp_otp_template and settings.whatsapp_results_template)
    return False


def destination(user: User, channel: str) -> str | None:
    return user.email if channel == "email" else user.whatsapp


def masked(channel: str, value: str | None) -> str | None:
    return mask_email(value) if channel == "email" else mask_phone(value)


def verified(user: User, channel: str) -> bool:
    return (user.email_verified_at if channel == "email" else user.whatsapp_verified_at) is not None


def test_mode_allows(channel: str, value: str | None) -> bool:
    """In delivery test mode only the configured test contacts may receive anything (codes or reports)."""
    if not settings.delivery_test_mode:
        return True
    if not value:
        return False
    if channel == "email":
        allowed = {e.strip().lower() for e in settings.delivery_test_emails.split(",") if e.strip()}
        return value.strip().lower() in allowed
    allowed = {normalize_whatsapp(n) for n in settings.delivery_test_whatsapp.split(",") if n.strip()} - {None}
    return normalize_whatsapp(value) in allowed


def same_contact(channel: str, a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    if channel == "email":
        return a.strip().lower() == b.strip().lower()
    return normalize_whatsapp(a) == normalize_whatsapp(b)


def blocker(user: User, channel: str, row: ResultDelivery | None = None) -> str | None:
    """Why the report can't be sent on this channel right now, or None when it can. With the report's delivery
    row: also refused when the account's contact is no longer the one the report was made for."""
    if not configured(channel):
        return "not_configured"
    if not destination(user, channel):
        return "no_contact"
    if row is not None and row.destination and not same_contact(channel, row.destination, destination(user, channel)):
        return "contact_changed"
    if not test_mode_allows(channel, destination(user, channel)):
        return "test_mode"
    if user.report_consent_at is None:
        return "no_consent"
    # mobile verification is the identity check for every report, whichever channel it goes to
    if user.whatsapp_verified_at is None:
        if channel == "email" and not (configured("whatsapp") and test_mode_allows("whatsapp", user.whatsapp)):
            return "mobile_verification_unavailable"  # no code can be sent to the mobile right now
        return "mobile_not_verified"
    if channel == "email" and settings.email_report_requires_email_verification and not verified(user, "email"):
        return "not_verified"
    return None


# ---------- providers ----------


def smtp_mode() -> str:
    """The SMTP encryption mode: "starttls" (port 587) or "ssl" (port 465); "none" only without a login.
    Anything else is refused, so a typo can never send the password unencrypted."""
    mode = (settings.smtp_security or "").strip().lower()
    if mode not in ("starttls", "ssl", "none"):
        raise DeliveryError(f"SMTP: SMTP_SECURITY must be starttls (port 587) or ssl (port 465), not {mode!r}")
    if mode == "none" and settings.smtp_username:
        raise DeliveryError("SMTP: refusing to send the login without encryption; set SMTP_SECURITY=starttls or ssl")
    return mode


def send_email(to: str, subject: str, text: str, html: str | None = None,
               attachments: list[tuple[str, bytes, str]] = (), message_id: str | None = None,
               reply_to: str | None = None) -> str:
    """Hand one email to the SMTP server (attachments: (filename, bytes, mime type)). Returns its Message-ID."""
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.smtp_from, to, subject
    if reply_to:
        msg["Reply-To"] = reply_to
    domain = settings.smtp_from.rsplit("@", 1)[-1].strip(" >") or None
    msg["Message-ID"] = message_id or make_msgid(domain=domain)
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    for filename, data, mime in attachments:
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    mode = smtp_mode()
    refused = None
    try:
        if mode == "ssl":  # TLS from the first byte (port 465)
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
        with server:
            if mode == "starttls":  # plain connection upgraded to TLS before the login (port 587)
                server.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            refused = server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        if refused is None:  # failed before the server took the message
            raise DeliveryError(f"SMTP: {type(exc).__name__}: {getattr(exc, 'smtp_error', b'') or exc}") from exc
        # the server had already accepted it (only the goodbye failed): reporting a failure would send it twice on retry
        logger.warning("SMTP: message accepted, but closing the connection failed: %s", type(exc).__name__)
    if refused:
        raise DeliveryError("SMTP: the recipient was refused")
    return msg["Message-ID"]


def upload_whatsapp_media(data: bytes, filename: str, mime: str = "application/pdf") -> str:
    """Upload a file to the WhatsApp Cloud API (POST /{phone-number-id}/media). Returns its media id."""
    url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/media"
    try:
        r = httpx.post(url, data={"messaging_product": "whatsapp", "type": mime}, files={"file": (filename, data, mime)},
                       headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"}, timeout=30)
    except httpx.HTTPError as exc:
        raise DeliveryError(f"WhatsApp media upload: {type(exc).__name__}") from exc
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code >= 400 or not body.get("id"):
        error = body.get("error") or {}
        raise DeliveryError(f"WhatsApp media upload: HTTP {r.status_code} {error.get('code', '')} {error.get('message', '')}".strip())
    return body["id"]


def delete_whatsapp_media(media_id: str) -> bool:
    """Delete an uploaded file from the WhatsApp Cloud API media store (DELETE /{media-id}). True when WhatsApp
    confirmed it, or it no longer exists there. Never raises: a failure is retried later (purge_whatsapp_media)."""
    url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{media_id}"
    try:
        r = httpx.delete(url, params={"phone_number_id": settings.whatsapp_phone_number_id},
                         headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"}, timeout=15)
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp media delete failed: %s", type(exc).__name__)
        return False
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code == 404 or (r.status_code < 400 and body.get("success") is True):
        return True
    logger.warning("WhatsApp media delete failed: HTTP %s", r.status_code)
    return False


TEMPLATE_PARAM_MAX = 200  # keeps the report's text variables well inside WhatsApp's 1024-character template body


def template_text(value: str, limit: int | None = None) -> str:
    """A WhatsApp template variable: WhatsApp refuses new lines, tabs and more than 4 spaces in a row, and empty text.
    With a limit, longer text is shortened with "…" (never used for the report link)."""
    text = re.sub(r"\s+", " ", str(value or "")).strip() or "-"
    return text if limit is None or len(text) <= limit else text[:limit - 1].rstrip(" ,") + "…"


def send_whatsapp_template(to: str, template: str, body_params: list[str], button_param: str | None = None,
                           header_document: dict | None = None) -> str:
    """Send an approved template through the WhatsApp Cloud API. Returns the WhatsApp message id (wamid),
    which only means WhatsApp ACCEPTED the message; sending/delivery is reported later by the webhook.
    header_document: {"id": <media id>, "filename": ...} for a template approved with a DOCUMENT header."""
    components = [{"type": "body", "parameters": [{"type": "text", "text": template_text(p)} for p in body_params]}]
    if header_document:
        components.insert(0, {"type": "header", "parameters": [{"type": "document", "document": header_document}]})
    if button_param is not None:  # authentication templates: the copy-code / one-tap URL button carries the code
        components.append({"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": button_param}]})
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to.lstrip("+"),
        "type": "template",
        "template": {"name": template, "language": {"code": settings.whatsapp_template_language}, "components": components},
    }
    url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages"
    try:
        r = httpx.post(url, json=payload, headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"}, timeout=20)
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:  # never reached WhatsApp: nothing was sent
        raise DeliveryError(f"WhatsApp: {type(exc).__name__}") from exc
    except httpx.HTTPError as exc:  # the request went out but no answer came back: it may have been sent
        raise DeliveryError(f"WhatsApp: {type(exc).__name__} (no answer from WhatsApp; the message may have been sent)") from exc
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code >= 400 or not (body.get("messages") or [{}])[0].get("id"):
        error = body.get("error") or {}
        raise DeliveryError(f"WhatsApp: HTTP {r.status_code} {error.get('code', '')} {error.get('message', '')}".strip())
    return body["messages"][0]["id"]


# ---------- one-time code: proving the contact is the user's ----------


def _code_hash(verification_id, code: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), f"{verification_id}:{code}".encode(), hashlib.sha256).hexdigest()


def _issue_code(db: Session, user: User, purpose: str, to: str, send) -> ContactVerification:
    """Rate-limit, record (HMAC only) and send one 6-digit code. purpose is stored as the verification's channel:
    "email" / "whatsapp" (confirming that contact) or "login" (signing in to an existing account by email).
    send(code) delivers it and raises DeliveryError on failure (then nothing is recorded)."""
    now = datetime.utcnow()
    recent = (db.query(ContactVerification)
              .filter(ContactVerification.user_id == user.id, ContactVerification.channel == purpose,
                      ContactVerification.created_at > now - timedelta(hours=1))
              .order_by(ContactVerification.created_at.desc()).all())
    if recent and now - recent[0].created_at < CODE_RESEND_AFTER:
        raise DeliveryRefused("A code was just sent. Please wait a minute before asking for another.", 429)
    if len(recent) >= CODES_PER_HOUR:
        raise DeliveryRefused("Too many codes requested. Please try again later.", 429)
    # the same limit per number/address across all accounts, so several sign-ups can't flood one phone
    to_destination = (db.query(ContactVerification)
                      .filter(ContactVerification.channel == purpose, ContactVerification.destination == to,
                              ContactVerification.created_at > now - timedelta(hours=1)).count())
    if to_destination >= CODES_PER_HOUR:
        raise DeliveryRefused("Too many codes requested. Please try again later.", 429)

    code = f"{secrets.randbelow(1_000_000):06d}"
    verification = ContactVerification(user_id=user.id, channel=purpose, destination=to, code_hash="", attempts=0,
                                       created_at=now, expires_at=now + CODE_TTL)
    db.add(verification)
    db.flush()
    verification.code_hash = _code_hash(verification.id, code)
    try:
        send(code)
    except DeliveryError as exc:
        db.rollback()
        logger.error("%s code to %s failed: %s", purpose, mask_email(to) if "@" in to else mask_phone(to), exc)
        raise DeliveryRefused("The code couldn't be sent right now. Please try again.", 502) from exc
    db.commit()
    logger.info("%s code sent to %s for user %s", purpose, mask_email(to) if "@" in to else mask_phone(to), user.id)
    return verification


def _check_code(db: Session, user: User, purpose: str, to: str | None, code: str) -> ContactVerification:
    """The user's latest open code for this purpose, marked used if `code` matches; DeliveryRefused otherwise."""
    now = datetime.utcnow()
    v = (db.query(ContactVerification)
         .filter(ContactVerification.user_id == user.id, ContactVerification.channel == purpose,
                 ContactVerification.verified_at.is_(None))
         .order_by(ContactVerification.created_at.desc()).first())
    if v is None or v.destination != to or v.expires_at < now:
        raise DeliveryRefused("This code has expired. Please ask for a new one.", 400)
    if v.attempts >= MAX_ATTEMPTS:
        raise DeliveryRefused("Too many wrong codes. Please ask for a new one.", 429)
    if not hmac.compare_digest(v.code_hash, _code_hash(v.id, (code or "").strip())):
        v.attempts += 1
        db.commit()
        raise DeliveryRefused("That code isn't right. Please check it and try again.", 400)
    v.verified_at = now
    return v


def start_verification(db: Session, user: User, channel: str) -> ContactVerification:
    """Send a 6-digit code to the user's own email / WhatsApp number."""
    if channel not in CHANNELS or not configured(channel):
        raise DeliveryRefused("Sending by this channel isn't set up yet.", 503)
    to = destination(user, channel)
    if not to:
        raise DeliveryRefused("There's no contact saved for this channel. Please enter your details again.", 400)
    if not test_mode_allows(channel, to):
        raise DeliveryRefused("Sending is limited to test contacts at the moment, so no code was sent.", 403)
    if verified(user, channel):
        raise DeliveryRefused("This contact is already confirmed.", 409)

    def send(code):
        if channel == "email":
            send_email(to, "Your YuriWoori verification code",
                       f"Your YuriWoori verification code is {code}. It expires in 10 minutes.\n\n"
                       "If you didn't ask for this code, you can ignore this email.")
        else:
            send_whatsapp_template(to, settings.whatsapp_otp_template, [code], button_param=code)
    return _issue_code(db, user, channel, to, send)


def confirm_verification(db: Session, user: User, channel: str, code: str) -> None:
    v = _check_code(db, user, channel, destination(user, channel), code)
    if channel == "email":
        user.email_verified_at = v.verified_at
    else:
        user.whatsapp_verified_at = v.verified_at
    db.commit()
    logger.info("User %s confirmed their %s", user.id, channel)


# ---------- signing in to an existing account (signup with an email that already has one) ----------
# Knowing a customer's email must not open their account (their skin results, their report contacts): a new
# device proves it with a code sent to that email. LOGIN is stored as the verification's channel.

LOGIN = "login"


def start_login(db: Session, user: User) -> ContactVerification:
    if not configured("email"):
        raise DeliveryRefused("This email already has an account. Signing in to it needs a code by email, which "
                              "can't be sent at the moment. Please try again later.", 503)
    if not test_mode_allows("email", user.email):
        raise DeliveryRefused("This email already has an account. Sign-in codes are limited to test contacts at "
                              "the moment, so no code was sent.", 403)
    return _issue_code(db, user, LOGIN, user.email, lambda code: send_email(
        user.email, "Your YuriWoori sign-in code",
        f"Your YuriWoori sign-in code is {code}. It expires in 10 minutes.\n\n"
        "Someone (hopefully you) entered this email to continue a YuriWoori skin analysis. "
        "If it wasn't you, ignore this email: nobody can open your results without this code."))


def confirm_login(db: Session, user: User, code: str) -> None:
    """The code proves the email is the user's: it also counts as email verification. Does not commit."""
    v = _check_code(db, user, LOGIN, user.email, code)
    user.email_verified_at = user.email_verified_at or v.verified_at


# ---------- the report messages ----------


def _money(value) -> str:
    return f"Rs. {value:,.0f}" if value is not None else ""


def report_messages(content: dict, link: str, reply_to: str | None = None) -> dict:
    """Email subject/text/html and WhatsApp template variables for a report (its saved content).
    reply_to: the team address replies go to (the email's Reply-To), mentioned in the email."""
    name = content.get("customer_name")
    concerns = ", ".join(c["phrase"] for c in content["concerns"]) or "no concerns above our levels"
    products = content["products"]
    am = ", ".join(products[s["handle"]]["name"] for s in content["routine"].get("AM", [])) or "-"
    pm = ", ".join(products[s["handle"]]["name"] for s in content["routine"].get("PM", [])) or "-"
    pricing = content.get("pricing")
    greeting = f"Hi {name}," if name else "Hi,"
    price_line = ""
    if pricing:
        discounts = "; ".join((f"coupon {d['title']}" if d.get("kind") == "code" else f"automatic discount {d['title']}, no code needed")
                              + f" -{_money(d['amount'])}" for d in pricing["discounts"])
        price_line = (f"Your routine on yuriwoori.com: subtotal {_money(pricing['subtotal'])}"
                      + (f", {discounts}" if discounts else "")
                      + f", total payable {_money(pricing['total'])} before shipping (priced by Shopify just now; shipping and"
                      " taxes are calculated at Shopify checkout).")
    else:
        price_line = "Final price unavailable - verify at Shopify checkout."

    text = "\n".join(filter(None, [
        greeting, "", "Your YuriWoori skin-analysis report is attached as a PDF.", "",
        f"Skin type: {content['skin_type']}" if content.get("skin_type") else None,
        f"Overall score: {content['overall_score']}/100" if content.get("overall_score") is not None else None,
        f"What we noticed: {concerns}", f"Morning routine: {am}", f"Evening routine: {pm}", price_line, "",
        f"View your report and continue to checkout: {link}",
        "This link is personal to you - please don't share it. It expires after a while; you can always run a new analysis.", "",
        f"Questions? Just reply to this email - it reaches our team at {reply_to}." if reply_to else None,
        content["disclaimer"],
    ]))
    html = ("<p>" + escape(greeting) + "</p><p>Your YuriWoori skin-analysis report is attached as a PDF.</p>"
            + (f"<p>Skin type: <b>{escape(content['skin_type'])}</b></p>" if content.get("skin_type") else "")
            + f"<p>What we noticed: {escape(concerns)}</p><p>Morning routine: {escape(am)}<br>Evening routine: {escape(pm)}</p>"
            + (f"<p>{escape(price_line)}</p>" if price_line else "")
            + f"<p><a href=\"{escape(link)}\">View your report and continue to checkout</a><br>"
              "<small>This link is personal to you - please don't share it.</small></p>"
            + (f"<p>Questions? Just reply to this email - it reaches our team at {escape(reply_to)}.</p>" if reply_to else "")
            + f"<p style=\"color:#666;font-size:12px\">{escape(content['disclaimer'])}</p>")
    # WhatsApp template variables can't contain line breaks: one line each
    return {"subject": "Your YuriWoori skin-analysis report", "text": text, "html": html,
            "whatsapp": [template_text(name or "there", 60), template_text(concerns, TEMPLATE_PARAM_MAX),
                         template_text(am, TEMPLATE_PARAM_MAX), template_text(pm, TEMPLATE_PARAM_MAX), link]}


# ---------- delivery: one row per report and channel ----------


def delivery_row(db: Session, report: Report, channel: str, lock: bool = False) -> ResultDelivery:
    """The report's delivery row for this channel (created "pending" if missing), bound to the owner's contact
    for this channel at that moment: the report is never sent to any other address or number."""
    query = db.query(ResultDelivery).filter(ResultDelivery.report_id == report.id, ResultDelivery.channel == channel)
    row = (query.with_for_update() if lock else query).first()
    if row is None:
        owner = db.get(User, report.user_id)
        try:
            with db.begin_nested():  # two requests may create it at once: the unique index lets one win
                db.add(ResultDelivery(user_id=report.user_id, scan_id=report.scan_id, report_id=report.id, channel=channel,
                                      status="pending", attempts=0, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
                                      destination=destination(owner, channel)))
        except IntegrityError:
            pass  # the other request created it
        row = (query.with_for_update() if lock else query).one()
    return row


def deliver(db: Session, user: User, report: Report, channel: str) -> ResultDelivery:
    """Send the report on one channel if it can and should be sent now; otherwise leave the row pending with
    the reason. Never sends a report the provider already has, and never twice at the same time."""
    now = datetime.utcnow()
    row = delivery_row(db, report, channel, lock=True)  # held until the commit below: concurrent requests wait
    if row.status in DONE or (row.status == "sending" and row.updated_at and now - row.updated_at < SENDING_TIMEOUT):
        db.commit()
        return row
    reason = blocker(user, channel, row)
    if reason:
        row.status, row.error, row.updated_at = "pending", reason, now
        db.commit()
        return row
    row.status, row.error, row.attempts, row.updated_at = "sending", None, row.attempts + 1, now
    db.commit()

    to = row.destination or destination(user, channel)  # the same contact the blocker just checked
    link = reports.report_url(report)
    reply_to = settings.delivery_reply_to or None
    media_id = None
    try:
        try:  # generated now, in memory, from this report's own scan; discarded after sending
            content = reports.content_for(db, report)
        except reports.ReportUnavailable as exc:
            raise DeliveryError("report_unavailable") from exc
        except LiveCatalogueUnavailable as exc:
            raise DeliveryError("catalogue_unavailable") from exc
        messages = report_messages(content, link, reply_to)
        if channel == "email":
            pdf = report_pdf.render(content, link)
            domain = settings.smtp_from.rsplit("@", 1)[-1].strip(" >")
            row.provider_message_id = send_email(
                to, messages["subject"], messages["text"], messages["html"],
                attachments=[("YuriWoori-skin-report.pdf", pdf, "application/pdf")],
                message_id=f"<report-{report.id}@{domain}>",  # the same id on a retry: mail clients show one message
                reply_to=reply_to)
            row.status, row.sent_at = "sent", datetime.utcnow()
        else:
            document = None
            if settings.whatsapp_results_template_has_document:  # the template was approved with a PDF document header
                media_id = upload_whatsapp_media(report_pdf.render(content, link), "YuriWoori-skin-report.pdf")
                document = {"id": media_id, "filename": "YuriWoori-skin-report.pdf"}
            row.provider_message_id = send_whatsapp_template(to, settings.whatsapp_results_template, messages["whatsapp"],
                                                             header_document=document)
            row.provider_media_id = media_id  # deleted from WhatsApp once delivered / read / failed
            row.status = "accepted"  # "sent" only when WhatsApp's webhook says so
    except DeliveryError as exc:
        row.status, row.error = "failed", str(exc)[:500]
        logger.error("Report %s to %s %s failed: %s", report.id, channel, masked(channel, to), exc)
        if media_id and not delete_whatsapp_media(media_id):  # uploaded, but the message wasn't sent
            row.provider_media_id = media_id  # purge_whatsapp_media retries the delete
    row.updated_at = datetime.utcnow()
    db.commit()
    if row.status != "failed":
        logger.info("Report %s %s by %s for %s", report.id, row.status, channel, masked(channel, to))
    return row


def deliver_all(db: Session, user: User, report: Report) -> list[ResultDelivery]:
    return [deliver(db, user, report, channel) for channel in CHANNELS]


def report_after_analysis(scan_id, user_id, db: Session | None = None) -> None:
    """Run after a finished analysis (background task): make the scan's report and send it on every channel that is
    ready. Only the scan's own owner, only their verified contact (deliver/blocker). Safe to run more than once and
    alongside the browser's own request: one report per scan, and a delivery the provider has is never sent again.
    Never raises."""
    own = db is None
    if own:
        from app.db.session import SessionLocal
        db = SessionLocal()
    try:
        from app.db.models import Scan
        scan, user = db.get(Scan, scan_id), db.get(User, user_id)
        if scan is None or user is None or scan.user_id != user.id:
            return
        report = reports.get_or_create(db, user, scan)
        if report.revoked_at is None:
            deliver_all(db, user, report)
        db.commit()
    except Exception as exc:  # logged by type only: never customer data
        logger.error("Report after analysis of scan %s not completed (%s)", scan_id, type(exc).__name__)
        db.rollback()
    finally:
        if own:
            db.close()


MEDIA_KEEP_AT_MOST = timedelta(days=7)  # an undeleted upload (no webhook) is removed after this


def purge_whatsapp_media(db: Session, older_than: timedelta = MEDIA_KEEP_AT_MOST) -> dict:
    """Delete report PDFs still in WhatsApp's media store for messages older than older_than (for when the
    status webhook isn't set up or a delete failed). WhatsApp removes uploads by itself after a while anyway."""
    rows = (db.query(ResultDelivery).filter(ResultDelivery.provider_media_id.isnot(None),
                                            ResultDelivery.updated_at < datetime.utcnow() - older_than).all())
    deleted = 0
    for row in rows:
        if configured("whatsapp") and delete_whatsapp_media(row.provider_media_id):
            row.provider_media_id = None
            deleted += 1
    db.commit()
    return {"due": len(rows), "deleted": deleted}


# ---------- WhatsApp status webhook ----------

WEBHOOK_STATUS = {"sent": "sent", "delivered": "delivered", "read": "delivered", "failed": "failed"}
_RANK = {"pending": 0, "sending": 1, "failed": 1, "accepted": 2, "sent": 3, "delivered": 4}


def valid_signature(raw_body: bytes, header: str | None) -> bool:
    """X-Hub-Signature-256: sha256=<HMAC of the raw body with the Meta app secret>."""
    if not settings.whatsapp_app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(settings.whatsapp_app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def apply_whatsapp_statuses(db: Session, payload: dict) -> int:
    """Update deliveries from a WhatsApp webhook payload; returns how many rows changed. A status never moves
    backwards (a late "sent" doesn't undo "delivered"); "failed" after acceptance is recorded."""
    changed = 0
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            for status in (change.get("value") or {}).get("statuses") or []:
                new = WEBHOOK_STATUS.get(status.get("status"))
                row = db.query(ResultDelivery).filter(ResultDelivery.provider_message_id == status.get("id"),
                                                      ResultDelivery.channel == "whatsapp").first()
                if not new or row is None:
                    continue
                if new == "failed":
                    if row.status in ("sent", "delivered"):
                        continue
                    errors = status.get("errors") or [{}]
                    row.error = f"WhatsApp: {errors[0].get('code', '')} {errors[0].get('title', '')}".strip()[:500]
                elif _RANK[new] <= _RANK.get(row.status, 0):
                    continue
                if new in ("sent", "delivered") and row.sent_at is None:
                    try:
                        row.sent_at = datetime.utcfromtimestamp(int(status.get("timestamp")))
                    except (TypeError, ValueError):
                        row.sent_at = datetime.utcnow()
                row.status, row.updated_at = new, datetime.utcnow()
                changed += 1
                # the device has the document (or never will): remove the PDF from WhatsApp's media store
                if row.provider_media_id and status.get("status") in ("delivered", "read", "failed"):
                    if delete_whatsapp_media(row.provider_media_id):
                        row.provider_media_id = None
    db.commit()
    return changed


# ---------- customers' WhatsApp replies -> the team ----------
# The Cloud API has no inbox: a message a customer sends to the business number only arrives on the webhook.
# Each one is forwarded by email to DELIVERY_REPLY_FORWARD_EMAIL (the team). Meta retries a webhook until it
# gets a 200, so already-forwarded message ids are remembered (this process) and never forwarded twice; if
# forwarding fails the webhook answers 503 and Meta retries later. Message text is never logged.

_forwarded_ids: dict[str, None] = {}  # insertion-ordered set of recent inbound message ids
_FORWARDED_KEEP = 5000


class ReplyForwardingFailed(RuntimeError):
    """A customer's WhatsApp message could not be forwarded to the team (the webhook should be retried)."""


def _message_text(message: dict) -> str:
    kind = message.get("type")
    if kind == "text":
        return (message.get("text") or {}).get("body", "")
    if kind == "button":
        return (message.get("button") or {}).get("text", "")
    if kind == "interactive":
        reply = (message.get("interactive") or {})
        chosen = reply.get("button_reply") or reply.get("list_reply") or {}
        return chosen.get("title", "")
    caption = (message.get(kind) or {}).get("caption") if isinstance(message.get(kind), dict) else None
    return f"[{kind} message{': ' + caption if caption else ''} - media is not forwarded; view it in WhatsApp Manager or your inbox tool]"


def forward_whatsapp_replies(db: Session, payload: dict) -> int:
    """Forward customers' incoming WhatsApp messages in a webhook payload to the team by email; returns how many
    were forwarded. Raises ReplyForwardingFailed when one couldn't be (so Meta retries the webhook)."""
    forwarded = 0
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts") or []}
            for message in value.get("messages") or []:
                message_id, sender = message.get("id"), message.get("from")
                if not message_id or not sender or message_id in _forwarded_ids:
                    continue
                number = "+" + sender.lstrip("+")
                if not (settings.delivery_reply_forward_email and configured("email")):
                    logger.warning("WhatsApp message from %s received but not forwarded: DELIVERY_REPLY_FORWARD_EMAIL "
                                   "or email (SMTP) isn't configured", mask_phone(number))
                    continue
                # several accounts may have entered this number: only one that proved it with a code is the sender
                customer = (db.query(User).filter(User.whatsapp == number, User.whatsapp_verified_at.isnot(None))
                            .order_by(User.whatsapp_verified_at.desc()).first())
                who = customer.name if customer and customer.name else names.get(sender) or "a customer"
                try:
                    when = datetime.utcfromtimestamp(int(message.get("timestamp"))).strftime("%Y-%m-%d %H:%M UTC")
                except (TypeError, ValueError):
                    when = "unknown time"
                text = "\n".join([
                    f"WhatsApp message to the YuriWoori business number from {who} ({number}), {when}:", "",
                    _message_text(message), "",
                    "Registered YuriWoori customer: " + ("yes" if customer else "no (no account has verified this number)"),
                    "Reply to the customer on WhatsApp from your WhatsApp inbox tool; this email address does not reach them.",
                ])
                try:
                    send_email(settings.delivery_reply_forward_email, f"WhatsApp message from {who} ({number})", text)
                except DeliveryError as exc:
                    logger.error("Forwarding a WhatsApp message from %s failed: %s", mask_phone(number), exc)
                    raise ReplyForwardingFailed(str(exc)) from exc
                _forwarded_ids[message_id] = None
                while len(_forwarded_ids) > _FORWARDED_KEEP:
                    _forwarded_ids.pop(next(iter(_forwarded_ids)))
                forwarded += 1
                logger.info("WhatsApp message from %s forwarded to the team", mask_phone(number))
    return forwarded
