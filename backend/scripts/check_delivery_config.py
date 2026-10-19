"""
Checks the report-delivery configuration in backend/.env WITHOUT sending any message:

- which settings are missing (names only, values are never printed);
- email: connects to the SMTP server, starts TLS and logs in, then disconnects (nothing is sent);
- WhatsApp: reads the phone number's details from the Cloud API and, when WHATSAPP_BUSINESS_ACCOUNT_ID is set,
  checks that the two templates exist, are APPROVED in WHATSAPP_TEMPLATE_LANGUAGE and have the right shape;
- delivery test mode: whether it is on, and how many test contacts are listed (masked).

    python scripts/check_delivery_config.py

Optionally, ONE test email (only on request, and only to an address listed in DELIVERY_TEST_EMAILS), sent with the
app's own sender and the same From / Reply-To as report emails:

    python scripts/check_delivery_config.py --send-test-email you@example.com
"""

import argparse

import os
import re
import smtplib
import ssl
import sys

import httpx

sys.path.append(os.getcwd())

from app.core.config import settings  # noqa: E402
from app.services.contact import mask_email, mask_phone, normalize_whatsapp  # noqa: E402

OK, BAD, INFO = "  [ok]  ", "  [!!]  ", "  [--]  "


def missing(*names) -> list[str]:
    return [n for n in names if not getattr(settings, n.lower())]


def check_email() -> bool:
    print("Email (SMTP)")
    gaps = missing("SMTP_HOST", "SMTP_FROM", "SMTP_USERNAME", "SMTP_PASSWORD")
    if gaps:
        print(BAD + "missing in backend/.env: " + ", ".join(gaps))
        return False
    from app.services.delivery import DeliveryError, smtp_mode
    try:
        mode = smtp_mode()
    except DeliveryError as exc:
        print(BAD + str(exc))
        return False
    expected_port = {"starttls": 587, "ssl": 465}.get(mode)
    if expected_port and settings.smtp_port != expected_port:
        print(BAD + f"SMTP_SECURITY={mode} goes with port {expected_port}, but SMTP_PORT={settings.smtp_port}: "
                    f"use 587 with starttls, or 465 with ssl")
        return False
    print(INFO + f"server {settings.smtp_host}:{settings.smtp_port} ({mode}), sender {settings.smtp_from}")
    try:
        if mode == "ssl":
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        with server:
            if mode == "starttls":
                server.starttls(context=ssl.create_default_context())
            server.login(settings.smtp_username, settings.smtp_password)
            server.noop()
    except smtplib.SMTPAuthenticationError as exc:
        print(BAD + f"login refused ({exc.smtp_code}). For Google Workspace use an App Password (needs 2-Step Verification).")
        return False
    except (smtplib.SMTPException, OSError) as exc:
        print(BAD + f"could not connect/log in: {type(exc).__name__}: {exc}")
        return False
    print(OK + "connected and logged in (no message sent)")
    sender = settings.smtp_from.rsplit("<", 1)[-1].strip(" >").lower()
    if settings.smtp_username.lower() != sender:
        print(INFO + "the sender address differs from the login: the account must be allowed to send as it (Gmail: 'Send mail as')")
    return True


def check_whatsapp() -> bool:
    print("WhatsApp (Cloud API)")
    gaps = missing("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_OTP_TEMPLATE", "WHATSAPP_RESULTS_TEMPLATE")
    if gaps:
        print(BAD + "missing in backend/.env: " + ", ".join(gaps))
        return False
    base = f"https://graph.facebook.com/{settings.whatsapp_api_version}"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    try:
        r = httpx.get(f"{base}/{settings.whatsapp_phone_number_id}", headers=headers, timeout=20,
                      params={"fields": "display_phone_number,verified_name,quality_rating,code_verification_status"})
        body = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        print(BAD + f"Cloud API not reachable: {type(exc).__name__}")
        return False
    if r.status_code != 200:
        error = body.get("error") or {}
        print(BAD + f"phone number lookup refused: HTTP {r.status_code} {error.get('code', '')} {error.get('message', '')}")
        return False
    print(OK + f"sending number {body.get('display_phone_number')} ({body.get('verified_name')}), quality {body.get('quality_rating')}")

    if not settings.whatsapp_business_account_id:
        print(INFO + "set WHATSAPP_BUSINESS_ACCOUNT_ID to also check the templates' approval status")
        return True
    try:
        r = httpx.get(f"{base}/{settings.whatsapp_business_account_id}/message_templates", headers=headers, timeout=20,
                      params={"fields": "name,status,language,category,components", "limit": 200})
        templates = r.json().get("data", []) if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        templates = None
    if templates is None:
        print(BAD + f"could not list templates (HTTP {r.status_code}); check the business account ID and token permissions")
        return False
    good = True
    for name, kind in ((settings.whatsapp_otp_template, "code"), (settings.whatsapp_results_template, "report")):
        t = next((t for t in templates if t["name"] == name and t["language"] == settings.whatsapp_template_language), None)
        if t is None:
            print(BAD + f"{kind} template '{name}' ({settings.whatsapp_template_language}) not found")
            good = False
            continue
        components = {c["type"]: c for c in t.get("components", [])}
        body_vars = len(set(re.findall(r"\{\{(\d+)\}\}", (components.get("BODY") or {}).get("text", ""))))
        problems = []
        if t["status"] != "APPROVED":
            problems.append(f"status {t['status']}")
        if kind == "code" and t.get("category") != "AUTHENTICATION":
            problems.append("category must be AUTHENTICATION")
        if kind == "report":
            if body_vars != 5:
                problems.append(f"body has {body_vars} variables, needs 5")
            has_doc = (components.get("HEADER") or {}).get("format") == "DOCUMENT"
            if has_doc != settings.whatsapp_results_template_has_document:
                problems.append(f"document header is {'present' if has_doc else 'absent'} but "
                                f"WHATSAPP_RESULTS_TEMPLATE_HAS_DOCUMENT={str(settings.whatsapp_results_template_has_document).lower()}")
        print((BAD if problems else OK) + f"{kind} template '{name}': " + ("; ".join(problems) if problems else "approved"))
        good = good and not problems
    return good


def check_test_mode():
    print("Delivery test mode")
    if not settings.delivery_test_mode:
        print(BAD + "OFF: codes and reports go to REAL customers who confirm their contacts")
        return
    emails = [e.strip() for e in settings.delivery_test_emails.split(",") if e.strip()]
    numbers = [n for n in (normalize_whatsapp(x) for x in settings.delivery_test_whatsapp.split(",") if x.strip())]
    print(OK + "ON: only these test contacts can receive anything")
    print(INFO + "test emails: " + (", ".join(mask_email(e) or "(invalid)" for e in emails) or "none (email sends nothing)"))
    print(INFO + "test WhatsApp: " + (", ".join(mask_phone(n) if n else "(invalid number)" for n in numbers) or "none (WhatsApp sends nothing)"))


def check_replies():
    print("Customer replies -> team")
    if settings.delivery_reply_to:
        print(OK + f"report emails: replies go to {settings.delivery_reply_to} (Reply-To)")
    else:
        print(BAD + f"report emails: no DELIVERY_REPLY_TO - replies go to the sender mailbox ({settings.smtp_from or 'not set'})")
    webhook = bool(settings.whatsapp_webhook_verify_token and settings.whatsapp_app_secret)
    if settings.delivery_reply_forward_email and webhook:
        print(OK + f"WhatsApp messages: forwarded by email to {settings.delivery_reply_forward_email} "
                   "(once the webhook is reachable over public HTTPS)")
    else:
        gaps = [n for n, v in (("DELIVERY_REPLY_FORWARD_EMAIL", settings.delivery_reply_forward_email),
                               ("WHATSAPP_WEBHOOK_VERIFY_TOKEN", settings.whatsapp_webhook_verify_token),
                               ("WHATSAPP_APP_SECRET", settings.whatsapp_app_secret)) if not v]
        print(BAD + "WhatsApp messages from customers are NOT reaching the team; missing: " + ", ".join(gaps)
              + " (and a public HTTPS address for /v1/delivery/whatsapp/webhook)")


def send_test_email(address: str, email_ok: bool) -> None:
    """One plain test email through the app's own sender (app/services/delivery.py). Only to a listed test address."""
    from app.services import delivery
    print("Test email")
    allowed = {e.strip().lower() for e in settings.delivery_test_emails.split(",") if e.strip()}
    if address.strip().lower() not in allowed:
        print(BAD + "not sent: the address must be listed in DELIVERY_TEST_EMAILS in backend/.env")
        return
    if not email_ok:
        print(BAD + "not sent: fix the email settings above first")
        return
    reply_to = settings.delivery_reply_to or None
    text = ("This is a test email from the YuriWoori skin-analysis app, sent to check the email settings.\n"
            "Customer reports use the same sender" + (f" and replies go to {reply_to}" if reply_to else "") + ".\n"
            "If it reached your inbox (not spam), email delivery works.")
    try:
        message_id = delivery.send_email(address, "YuriWoori email test", text, reply_to=reply_to)
    except delivery.DeliveryError as exc:
        print(BAD + f"not accepted by the SMTP server: {exc}")
        return
    print(OK + f"accepted by the SMTP server for {mask_email(address)} (Message-ID {message_id})")
    print(INFO + f"From: {settings.smtp_from}" + (f" | Reply-To: {reply_to}" if reply_to else " | no Reply-To"))
    print(INFO + "accepted is not delivered: check the inbox (and the spam folder) of that address")


def main():
    parser = argparse.ArgumentParser(description="Check the report-delivery configuration (sends nothing by default).")
    parser.add_argument("--send-test-email", metavar="ADDRESS",
                        help="send ONE test email to this address (must be listed in DELIVERY_TEST_EMAILS)")
    args = parser.parse_args()
    email_ok = check_email()
    whatsapp_ok = check_whatsapp()
    check_test_mode()
    check_replies()
    print("Report links")
    url = settings.frontend_public_url
    print((INFO if url.startswith("http://localhost") or url.startswith("http://127.") else OK)
          + f"FRONTEND_PUBLIC_URL = {url}" + (" (links only open on this PC)" if "localhost" in url or "127.0.0.1" in url else ""))
    print("Who must verify what")
    print(INFO + "mobile (WhatsApp) code: required before ANY report is sent, by email too")
    print(INFO + "email code: " + ("required as well" if settings.email_report_requires_email_verification
                                    else "not required (EMAIL_REPORT_REQUIRES_EMAIL_VERIFICATION=false)"))
    if not whatsapp_ok:
        print(BAD + "WhatsApp isn't ready, so no mobile number can be verified and NO report can be sent (email included)")
    if args.send_test_email:
        send_test_email(args.send_test_email, email_ok)
    print("\nResult: email " + ("ready" if email_ok else "NOT ready") + ", WhatsApp " + ("ready" if whatsapp_ok else "NOT ready")
          + (". Only the test email above was attempted." if args.send_test_email else ". Nothing was sent."))


if __name__ == "__main__":
    main()
