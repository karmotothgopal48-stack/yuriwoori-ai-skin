"""
The report delivery flow end to end on the real database (rolled back; skipped without PostgreSQL):
saved scan -> report (saved results + live catalogue + Shopify pricing, stubbed) -> consent -> one-time code ->
email with PDF / WhatsApp with link -> delivery status, webhook updates, retries -> secure report link.
The providers are stubbed: these tests check WHO gets WHAT and WHEN, and what is recorded.
"""

import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import ContactVerification, Report, ResultDelivery, Scan, User
from app.main import app
from app.services import delivery, reports
from conftest import make_scan
from tests_support import stub_shopify_pricing

client = TestClient(app)


@pytest.fixture
def outbox(monkeypatch):
    """Email and WhatsApp configured, with the providers replaced by an outbox; Shopify pricing stubbed."""
    sent = []
    stub_shopify_pricing(monkeypatch)
    for key, value in (("smtp_host", "smtp.example.com"), ("smtp_from", "YuriWoori <care@example.com>"),
                       ("whatsapp_access_token", "t"), ("whatsapp_phone_number_id", "1"), ("whatsapp_otp_template", "yuriwoori_code"),
                       ("whatsapp_results_template", "yuriwoori_report"), ("whatsapp_app_secret", "app-secret"),
                       ("frontend_public_url", "https://skin.yuriwoori.com"), ("delivery_test_mode", False),
                       ("delivery_reply_to", "team@example.com"), ("delivery_reply_forward_email", ""),
                       ("email_report_requires_email_verification", False)):
        monkeypatch.setattr(settings, key, value)

    def email(to, subject, text, html=None, attachments=(), message_id=None, reply_to=None):
        sent.append({"channel": "email", "to": to, "subject": subject, "text": text, "attachments": list(attachments), "message_id": message_id, "reply_to": reply_to})
        return message_id or "<code@example.com>"

    def whatsapp(to, template, params, button_param=None, header_document=None):
        sent.append({"channel": "whatsapp", "to": to, "template": template, "params": params, "document": header_document})
        return f"wamid.{len(sent)}"

    monkeypatch.setattr(delivery, "send_email", email)
    monkeypatch.setattr(delivery, "send_whatsapp_template", whatsapp)
    return sent


def consenting_scan(db, **kw):
    s = make_scan(db, **kw)
    db.get(User, s.user_id).report_consent_at = datetime.utcnow()
    db.flush()
    return s


def code_from(sent) -> str:
    last = sent[-1]
    return re.search(r"\d{6}", last["text"] if last["channel"] == "email" else last["params"][0]).group(0)


def confirm(scan, channel, sent):
    assert client.post("/v1/delivery/verify/start", headers=scan.headers, json={"channel": channel}).status_code == 200
    r = client.post("/v1/delivery/verify/confirm", headers=scan.headers, json={"channel": channel, "code": code_from(sent)})
    assert r.status_code == 200, r.text
    return r.json()


def statuses(scan):
    r = client.get(f"/v1/reports/scan/{scan.id}", headers=scan.headers)
    assert r.status_code == 200, r.text
    return {d["channel"]: d for d in r.json()["deliveries"]}


def signed(body: dict) -> dict:
    raw = json.dumps(body).encode()
    return {"content": raw, "headers": {"Content-Type": "application/json",
                                        "X-Hub-Signature-256": "sha256=" + hmac.new(b"app-secret", raw, hashlib.sha256).hexdigest()}}


def webhook(message_id, status, **extra):
    return {"entry": [{"changes": [{"value": {"statuses": [{"id": message_id, "status": status, "timestamp": "1791300000", **extra}]}}]}]}


def test_not_configured_channels_stay_pending_and_nothing_is_sent(db, monkeypatch):
    stub_shopify_pricing(monkeypatch)
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "whatsapp_access_token", "")
    scan = consenting_scan(db)
    r = client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)})
    assert r.status_code == 200, r.text
    d = {x["channel"]: x for x in r.json()["deliveries"]}
    assert d["email"]["status"] == d["whatsapp"]["status"] == "pending"
    assert d["email"]["reason"] == d["whatsapp"]["reason"] == "not_configured" and not d["email"]["can_retry"]
    assert d["email"]["sent_at"] is None


def test_email_waits_with_a_clear_reason_when_no_mobile_code_can_be_sent(db, outbox, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_access_token", "")  # WhatsApp not set up: the mobile can't be verified
    scan = consenting_scan(db)
    d = {x["channel"]: x for x in client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)}).json()["deliveries"]}
    assert d["whatsapp"]["reason"] == "not_configured" and d["email"]["reason"] == "mobile_verification_unavailable"
    assert d["email"]["status"] == "pending" and not d["email"]["can_retry"] and outbox == []


def test_the_report_is_built_once_from_the_saved_scan(db, outbox):
    scan = consenting_scan(db)
    first = client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)}).json()
    again = client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)}).json()
    assert first["report_id"] == again["report_id"]
    report = db.query(Report).filter(Report.scan_id == scan.id).one()
    assert report.content is None  # nothing of the report is stored
    content = reports.content_for(db, report)  # generated in memory from the saved analysis
    assert {m["key"]: m["value"] for m in content["metrics"]}["hydration"] == 30  # the saved profile's value
    assert content["pricing"]["total"] == 4440.0 and report.token_hash and len(report.token_hash) == 64
    assert (report.expires_at - report.created_at).days == settings.report_link_days


def test_without_consent_nothing_is_sent_even_when_confirmed(db, outbox):
    scan = make_scan(db)  # signed up without agreeing to have the report sent
    confirm(scan, "email", outbox)
    client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)})
    assert [m for m in outbox if m.get("attachments")] == []
    assert statuses(scan)["email"]["reason"] == "no_consent"


def test_email_report_goes_out_once_after_the_mobile_number_is_verified(db, outbox):
    """Mobile verification is compulsory; the email address itself needs no code (optional email verification)."""
    scan = consenting_scan(db)
    created = {d["channel"]: d for d in client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)}).json()["deliveries"]}
    assert created["email"]["status"] == "pending" and created["email"]["reason"] == "mobile_not_verified"
    assert created["whatsapp"]["reason"] == "mobile_not_verified"
    assert outbox == []  # nothing goes out before the mobile number is verified

    confirmed = confirm(scan, "whatsapp", outbox)  # the mobile code releases both waiting reports
    assert {d["channel"]: d["status"] for d in confirmed["deliveries"]} == {"email": "sent", "whatsapp": "accepted"}
    user = db.get(User, scan.user_id)
    assert user.email_verified_at is None  # the email was not verified, and is not labelled verified
    mail = next(m for m in reversed(outbox) if m["channel"] == "email")
    assert mail["to"] == user.email and mail["subject"] == "Your YuriWoori skin-analysis report"
    assert mail["reply_to"] == "team@example.com"  # the customer's reply reaches the team
    [(name, pdf, mime)] = mail["attachments"]
    assert (name, mime) == ("YuriWoori-skin-report.pdf", "application/pdf") and pdf.startswith(b"%PDF-")
    link = re.search(r"https://skin\.yuriwoori\.com/report#t=([\w-]+)", mail["text"])
    assert link and mail["message_id"].startswith("<report-")
    row = db.query(ResultDelivery).filter(ResultDelivery.scan_id == scan.id, ResultDelivery.channel == "email").one()
    assert (row.status, row.attempts) == ("sent", 1) and row.sent_at is not None

    # asking again (or a double click) does not send it twice
    sends = len(outbox)
    r = client.post(f"/v1/delivery/scans/{scan.id}/send", headers=scan.headers, json={"channel": "email"})
    assert r.status_code == 200 and r.json()["status"] == "sent" and len(outbox) == sends
    assert db.query(ResultDelivery).filter(ResultDelivery.scan_id == scan.id, ResultDelivery.channel == "email").count() == 1


def test_email_verification_can_still_be_required_by_policy(db, outbox, monkeypatch):
    monkeypatch.setattr(settings, "email_report_requires_email_verification", True)
    scan = consenting_scan(db)
    client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)})
    confirm(scan, "whatsapp", outbox)
    assert statuses(scan)["email"]["reason"] == "not_verified" and not any(m.get("attachments") for m in outbox)
    confirm(scan, "email", outbox)  # the optional email code, required by this policy
    assert statuses(scan)["email"]["status"] == "sent"


def test_whatsapp_report_is_accepted_then_confirmed_by_the_webhook(db, outbox):
    scan = consenting_scan(db)
    client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)})
    confirmed = confirm(scan, "whatsapp", outbox)
    assert {d["channel"]: d["status"] for d in confirmed["deliveries"]}["whatsapp"] == "accepted"  # WhatsApp took it; not yet "sent"
    msg = next(m for m in reversed(outbox) if m["channel"] == "whatsapp")
    assert msg["template"] == "yuriwoori_report" and msg["to"] == "+919876543210" and len(msg["params"]) == 5
    assert msg["params"][4].startswith("https://skin.yuriwoori.com/report#t=") and all("\n" not in p for p in msg["params"])
    wamid = db.query(ResultDelivery).filter(ResultDelivery.scan_id == scan.id, ResultDelivery.channel == "whatsapp").one().provider_message_id

    assert client.post("/v1/delivery/whatsapp/webhook", content=json.dumps(webhook(wamid, "sent")),
                       headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=forged"}).status_code == 403
    assert statuses(scan)["whatsapp"]["status"] == "accepted"
    assert client.post("/v1/delivery/whatsapp/webhook", **signed(webhook(wamid, "sent"))).json() == {"updated": 1, "forwarded": 0}
    s = statuses(scan)["whatsapp"]
    assert s["status"] == "sent" and s["sent_at"].startswith("2026-")
    client.post("/v1/delivery/whatsapp/webhook", **signed(webhook(wamid, "delivered")))
    client.post("/v1/delivery/whatsapp/webhook", **signed(webhook(wamid, "sent")))  # late, out of order: ignored
    assert statuses(scan)["whatsapp"]["status"] == "delivered"


def test_a_whatsapp_failure_reported_by_the_webhook_is_recorded(db, outbox):
    scan = consenting_scan(db)
    client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)})
    confirm(scan, "whatsapp", outbox)
    wamid = db.query(ResultDelivery).filter(ResultDelivery.scan_id == scan.id, ResultDelivery.channel == "whatsapp").one().provider_message_id
    client.post("/v1/delivery/whatsapp/webhook", **signed(webhook(wamid, "failed", errors=[{"code": 131026, "title": "Message undeliverable"}])))
    s = statuses(scan)["whatsapp"]
    assert s["status"] == "failed" and s["can_retry"]


def test_a_provider_failure_is_recorded_and_can_be_retried_safely(db, outbox, monkeypatch):
    scan = consenting_scan(db)
    original = delivery.send_email
    confirm(scan, "whatsapp", outbox)  # the mobile is verified...

    def down(*a, **k):
        raise delivery.DeliveryError("SMTP: OSError: connection refused")
    monkeypatch.setattr(delivery, "send_email", down)  # ...then the mail server goes down
    r = client.post(f"/v1/delivery/scans/{scan.id}/send", headers=scan.headers, json={"channel": "email"})
    assert r.status_code == 200 and r.json()["status"] == "failed" and r.json()["can_retry"] and r.json()["sent_at"] is None
    row = db.query(ResultDelivery).filter(ResultDelivery.scan_id == scan.id, ResultDelivery.channel == "email").one()
    assert "connection refused" in row.error

    monkeypatch.setattr(delivery, "send_email", original)  # back up: the retry sends it, once
    r = client.post(f"/v1/delivery/scans/{scan.id}/send", headers=scan.headers, json={"channel": "email"})
    assert r.json()["status"] == "sent" and r.json()["attempts"] == 2
    assert len([m for m in outbox if m.get("attachments")]) == 1


def test_a_send_already_in_progress_is_not_started_again(db, outbox):
    scan = consenting_scan(db)
    confirm(scan, "whatsapp", outbox)
    report = reports.get_or_create(db, db.get(User, scan.user_id), db.get(Scan, scan.id))
    row = delivery.delivery_row(db, report, "email")
    row.status, row.updated_at = "sending", datetime.utcnow()
    db.commit()
    before = len(outbox)
    assert delivery.deliver(db, db.get(User, scan.user_id), report, "email").status == "sending" and len(outbox) == before
    row.updated_at = datetime.utcnow() - timedelta(minutes=10)  # stuck (e.g. a crash): may be retried
    db.commit()
    assert delivery.deliver(db, db.get(User, scan.user_id), report, "email").status == "sent" and len(outbox) == before + 1


def test_the_secure_link_opens_the_report_until_it_expires_or_is_withdrawn(db, outbox):
    scan = consenting_scan(db)
    client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)})
    confirm(scan, "whatsapp", outbox)
    token = re.search(r"report#t=([\w-]+)", next(m for m in outbox if m.get("attachments"))["text"]).group(1)

    r = client.get("/v1/reports/shared", headers={"X-Report-Token": token})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store" and r.headers["referrer-policy"] == "no-referrer"
    content = r.json()["content"]
    assert content["customer_name"] == "Test" and content["pricing"]["total"] == 4440.0
    user = db.get(User, scan.user_id)
    assert user.email not in json.dumps(content) and user.whatsapp not in json.dumps(content)  # no contact details
    pdf = client.get("/v1/reports/shared/pdf", headers={"X-Report-Token": token})
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF-")

    for bad in (None, "", token[:-1] + ("A" if token[-1] != "A" else "B"), "x" * 500):
        headers = {"X-Report-Token": bad} if bad is not None else {}
        assert client.get("/v1/reports/shared", headers=headers).status_code == 404

    report = db.query(Report).filter(Report.scan_id == scan.id).one()
    report.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.flush()
    assert client.get("/v1/reports/shared", headers={"X-Report-Token": token}).status_code == 404  # expired
    report.expires_at = datetime.utcnow() + timedelta(days=1)
    db.flush()
    assert client.post(f"/v1/reports/scan/{scan.id}/revoke", headers=scan.headers).json()["revoked"] is True
    assert client.get("/v1/reports/shared", headers={"X-Report-Token": token}).status_code == 404  # withdrawn


def test_nobody_can_get_or_send_another_customers_report(db, outbox):
    scan = consenting_scan(db)
    other = consenting_scan(db, email_prefix="other-customer")
    for call in (lambda h: client.post("/v1/reports", headers=h, json={"scan_id": str(scan.id)}),
                 lambda h: client.get(f"/v1/reports/scan/{scan.id}", headers=h),
                 lambda h: client.get(f"/v1/reports/scan/{scan.id}/pdf", headers=h),
                 lambda h: client.post(f"/v1/reports/scan/{scan.id}/revoke", headers=h),
                 lambda h: client.post(f"/v1/delivery/scans/{scan.id}/send", headers=h, json={"channel": "email"})):
        assert call(other.headers).status_code == 403
        assert call({}).status_code == 401
    assert outbox == []


def test_signup_records_report_consent_explicitly(db, outbox):
    email = f"consent-{datetime.utcnow().timestamp()}@example.com"
    body = {"name": "A", "whatsapp": "9876543210", "email": email, "consent": True}
    first = client.post("/v1/users/signup", json=body).json()
    assert first["user"]["report_consent"] is False
    own = {"Authorization": f"Bearer {first['token']}"}  # the same browser, signed in: no code needed
    assert client.post("/v1/users/signup", headers=own, json={**body, "report_consent": True}).json()["user"]["report_consent"] is True
    assert client.post("/v1/users/signup", headers=own, json=body).json()["user"]["report_consent"] is False  # withdrawn
    assert outbox == []


def test_an_existing_email_only_opens_with_the_code_sent_to_it(db, outbox):
    """Knowing a customer's email must not open their account: a new device gets a code emailed to that address."""
    scan = make_scan(db, email_prefix="existing-account")
    owner = db.get(User, scan.user_id)
    body = {"name": "Someone", "whatsapp": "+447700900999", "email": owner.email.upper(), "consent": True}

    r = client.post("/v1/users/signup", json=body)
    assert r.status_code == 200 and r.json()["code_required"] and r.json()["token"] is None and r.json()["user"] is None
    assert r.json()["sent_to"] != owner.email and "@example.com" in r.json()["sent_to"]  # masked
    assert [m["to"] for m in outbox] == [owner.email] and "sign-in code" in outbox[0]["subject"]
    assert db.get(User, scan.user_id).whatsapp == "+919876543210"  # nothing changed without the code
    code = code_from(outbox)

    # someone else's session doesn't count, and wrong codes are refused (and limited)
    stranger = client.post("/v1/users/signup", json={**body, "email": f"stranger-{uuid.uuid4().hex}@example.com"}).json()
    r = client.post("/v1/users/signup", headers={"Authorization": f"Bearer {stranger['token']}"}, json=body)
    assert r.status_code == 429 and not r.json().get("token")  # not opened (and no second code within a minute)
    assert client.post("/v1/users/signup", json={**body, "code": "000000" if code != "000000" else "111111"}).status_code == 400

    r = client.post("/v1/users/signup", json={**body, "code": code})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["id"] == str(owner.id) and r.json()["token"] and r.json()["user"]["email_verified"]
    assert r.json()["user"]["whatsapp"] == "+447700900999" and not r.json()["user"]["whatsapp_verified"]
    assert client.post("/v1/users/signup", json={**body, "code": code}).status_code == 400  # a code works once


def test_an_existing_email_without_working_email_is_refused_not_opened(db, monkeypatch):
    scan = make_scan(db, email_prefix="no-smtp")
    monkeypatch.setattr(settings, "smtp_host", "")
    r = client.post("/v1/users/signup", json={"name": "X", "whatsapp": "9876543210", "email": db.get(User, scan.user_id).email, "consent": True})
    assert r.status_code == 503 and "token" not in r.text


def test_codes_expire_and_cannot_be_guessed_forever(db, outbox):
    scan = consenting_scan(db)
    client.post("/v1/delivery/verify/start", headers=scan.headers, json={"channel": "email"})
    code = code_from(outbox)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(delivery.MAX_ATTEMPTS):
        client.post("/v1/delivery/verify/confirm", headers=scan.headers, json={"channel": "email", "code": wrong})
    assert client.post("/v1/delivery/verify/confirm", headers=scan.headers, json={"channel": "email", "code": code}).status_code == 429
    v = db.query(ContactVerification).filter(ContactVerification.user_id == scan.user_id).one()
    v.attempts, v.expires_at = 0, v.expires_at - timedelta(minutes=30)
    db.flush()
    assert client.post("/v1/delivery/verify/confirm", headers=scan.headers, json={"channel": "email", "code": code}).status_code == 400


def test_no_report_goes_out_on_any_channel_before_the_mobile_is_verified(db, outbox):
    scan = consenting_scan(db)
    client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)})
    confirm(scan, "email", outbox)  # an email code alone is not enough: the mobile number is the identity check
    for channel in ("email", "whatsapp"):
        r = client.post(f"/v1/delivery/scans/{scan.id}/send", headers=scan.headers, json={"channel": channel})
        assert r.json()["status"] == "pending" and r.json()["reason"] == "mobile_not_verified"
    assert not any(m.get("attachments") or m.get("template") == "yuriwoori_report" for m in outbox)
    assert db.query(ResultDelivery).join(Report).filter(Report.scan_id == scan.id, ResultDelivery.sent_at.isnot(None)).count() == 0


def test_a_wrong_code_does_not_verify_the_mobile_and_a_code_is_single_use(db, outbox):
    scan = consenting_scan(db)
    client.post("/v1/delivery/verify/start", headers=scan.headers, json={"channel": "whatsapp"})
    code = code_from(outbox)
    wrong = "000000" if code != "000000" else "111111"
    assert client.post("/v1/delivery/verify/confirm", headers=scan.headers, json={"channel": "whatsapp", "code": wrong}).status_code == 400
    assert db.get(User, scan.user_id).whatsapp_verified_at is None
    assert client.post("/v1/delivery/verify/confirm", headers=scan.headers, json={"channel": "whatsapp", "code": code}).status_code == 200
    assert db.get(User, scan.user_id).whatsapp_verified_at is not None
    v = db.query(ContactVerification).filter(ContactVerification.user_id == scan.user_id).one()
    assert code not in v.code_hash and len(v.code_hash) == 64  # only a keyed hash of the code is stored
    # asking for another code too soon is refused
    other = consenting_scan(db, email_prefix="resend", whatsapp="+447700900555")
    client.post("/v1/delivery/verify/start", headers=other.headers, json={"channel": "whatsapp"})
    assert client.post("/v1/delivery/verify/start", headers=other.headers, json={"channel": "whatsapp"}).status_code == 429


def test_one_mobile_number_cannot_be_flooded_with_codes_from_many_accounts(db, outbox):
    number = f"+44770090{datetime.utcnow().microsecond % 10000:04d}"
    first = consenting_scan(db, email_prefix="flood-a", whatsapp=number)
    to = delivery.destination(db.get(User, first.user_id), "whatsapp")
    now = datetime.utcnow()
    for i in range(delivery.CODES_PER_HOUR):  # five codes already went to this number from other sign-ups
        db.add(ContactVerification(user_id=first.user_id, channel="whatsapp", destination=to, code_hash="x",
                                   attempts=0, created_at=now - timedelta(minutes=2 + i), expires_at=now))
    db.flush()
    second = consenting_scan(db, email_prefix="flood-b", whatsapp=number)
    sends = len(outbox)
    r = client.post("/v1/delivery/verify/start", headers=second.headers, json={"channel": "whatsapp"})
    assert r.status_code == 429 and len(outbox) == sends


def test_an_invalid_request_is_rejected_without_repeating_what_was_sent(db):
    scan = make_scan(db)
    marker = "PRIVATE-PHOTO-DATA-0123456789"
    r = client.post(f"/v1/scans/{scan.id}/analyze", headers=scan.headers, json={"image_base64": [marker]})
    assert r.status_code == 422 and marker not in r.text and "input" not in r.json()["detail"][0]
    r = client.post("/v1/users/signup", json={"name": "A", "whatsapp": ["+919876543210"], "email": marker, "consent": True})
    assert r.status_code == 422 and marker not in r.text and "+919876543210" not in r.text


def test_a_report_is_never_sent_to_a_number_added_after_it_was_made(db, outbox):
    """Changing the account's WhatsApp number must not route a waiting report to the new number, even once that
    number is verified: the report goes only to the contact it was made for."""
    scan = consenting_scan(db, email_prefix="report-owner")
    owner = db.get(User, scan.user_id)
    client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)})  # waits for the mobile code
    row = db.query(ResultDelivery).filter(ResultDelivery.scan_id == scan.id, ResultDelivery.channel == "whatsapp").one()
    assert row.destination == owner.whatsapp

    # the owner changes their number (their own session; a stranger can't: see the sign-in code test above)
    other = client.post("/v1/users/signup", headers=scan.headers, json={"name": "Someone", "whatsapp": "+447700900999",
                                                                       "email": owner.email, "consent": True, "report_consent": True}).json()
    headers = {"Authorization": f"Bearer {other['token']}"}
    assert client.post("/v1/delivery/verify/start", headers=headers, json={"channel": "whatsapp"}).status_code == 200
    r = client.post("/v1/delivery/verify/confirm", headers=headers, json={"channel": "whatsapp", "code": code_from(outbox)})
    assert r.status_code == 200
    assert not any(m["channel"] == "whatsapp" and m["template"] == "yuriwoori_report" for m in outbox)  # nothing to the new number
    s = statuses(scan)["whatsapp"]
    assert s["status"] == "pending" and s["reason"] == "contact_changed" and not s["can_retry"]
    r = client.post(f"/v1/delivery/scans/{scan.id}/send", headers=headers, json={"channel": "whatsapp"})
    assert r.json()["reason"] == "contact_changed"
    assert not any(m["channel"] == "whatsapp" and m["template"] == "yuriwoori_report" for m in outbox)
    # the email copy can only ever go to the account's own address (the report owner's)
    assert all(m["to"] == owner.email for m in outbox if m["channel"] == "email")


def test_whatsapp_webhook_subscription_check(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_webhook_verify_token", "verify-me")
    ok = client.get("/v1/delivery/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    assert client.get("/v1/delivery/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"}).status_code == 403


# ---------- the automatic workflow: details + consent -> contacts confirmed at signup -> analysis -> report sent ----------


def test_report_is_sent_automatically_after_the_analysis_to_the_customers_own_contacts(db, outbox):
    """Signup with consent, contacts confirmed right after signup (before the scan), then the analysis is saved
    and the frontend's automatic POST /reports sends the report — no further action by the customer."""
    customer = consenting_scan(db, email_prefix="auto-delivery")  # a saved analysis for this customer
    other = consenting_scan(db, email_prefix="someone-else", whatsapp="+447700900123")
    confirm(customer, "email", outbox)
    confirm(customer, "whatsapp", outbox)
    before = len(outbox)

    r = client.post("/v1/reports", headers=customer.headers, json={"scan_id": str(customer.id)})  # what analyzeSkin() calls
    assert r.status_code == 200
    statuses_now = {d["channel"]: d["status"] for d in r.json()["deliveries"]}
    assert statuses_now == {"email": "sent", "whatsapp": "accepted"}  # WhatsApp: accepted, awaiting WhatsApp's confirmation

    sent = outbox[before:]
    user, someone_else = db.get(User, customer.user_id), db.get(User, other.user_id)
    assert [m["to"] for m in sent] == [user.email, user.whatsapp]  # exactly this customer's own contacts
    assert someone_else.email not in [m["to"] for m in sent] and someone_else.whatsapp not in [m["to"] for m in sent]
    assert sent[0]["attachments"][0][2] == "application/pdf"

    # the routine page asks again (and a second analysis request may race it): nothing is sent twice
    client.post("/v1/reports", headers=customer.headers, json={"scan_id": str(customer.id)})
    assert len(outbox) == before + 2


def test_whatsapp_report_carries_the_pdf_when_the_template_has_a_document_header(db, outbox, monkeypatch):
    uploads = []
    monkeypatch.setattr(settings, "whatsapp_results_template_has_document", True)
    monkeypatch.setattr(delivery, "upload_whatsapp_media", lambda data, filename, mime="application/pdf": (uploads.append((data[:5], filename)), "MEDIA9")[1])
    scan = consenting_scan(db)
    confirm(scan, "whatsapp", outbox)
    client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)})
    assert uploads == [(b"%PDF-", "YuriWoori-skin-report.pdf")]
    msg = outbox[-1]
    assert msg["template"] == "yuriwoori_report" and msg["document"] == {"id": "MEDIA9", "filename": "YuriWoori-skin-report.pdf"}
    assert msg["params"][4].startswith("https://skin.yuriwoori.com/report#t=")  # the secure link is still included


def test_a_failed_pdf_upload_records_failure_sends_nothing_and_can_be_retried(db, outbox, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_results_template_has_document", True)

    def refused(*a, **k):
        raise delivery.DeliveryError("WhatsApp media upload: HTTP 400 131053 Media upload error")
    monkeypatch.setattr(delivery, "upload_whatsapp_media", refused)
    scan = consenting_scan(db)
    confirm(scan, "whatsapp", outbox)  # confirmed at signup
    whatsapp_sent = lambda: [m for m in outbox if m["channel"] == "whatsapp"]  # noqa: E731
    before = len(whatsapp_sent())
    client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)})  # analysis done: report fails at the upload
    s = statuses(scan)["whatsapp"]
    assert s["status"] == "failed" and s["can_retry"] and len(whatsapp_sent()) == before  # no WhatsApp report went out
    assert statuses(scan)["email"]["status"] == "sent"  # the email channel is independent
    monkeypatch.setattr(delivery, "upload_whatsapp_media", lambda data, filename, mime="application/pdf": "MEDIA10")
    r = client.post(f"/v1/delivery/scans/{scan.id}/send", headers=scan.headers, json={"channel": "whatsapp"})
    assert r.json()["status"] == "accepted" and len(whatsapp_sent()) == before + 1 and whatsapp_sent()[-1]["document"]["id"] == "MEDIA10"


def test_test_mode_sends_only_to_the_listed_test_contacts(db, outbox, monkeypatch):
    tester = consenting_scan(db, email_prefix="tester")
    customer = consenting_scan(db, email_prefix="real-customer", whatsapp="+447700900123")
    monkeypatch.setattr(settings, "delivery_test_mode", True)
    monkeypatch.setattr(settings, "delivery_test_emails", db.get(User, tester.user_id).email.upper())
    monkeypatch.setattr(settings, "delivery_test_whatsapp", "98765 43210")  # any format matches +919876543210

    # a real customer: no code, no report, and the reason is shown
    assert client.post("/v1/delivery/verify/start", headers=customer.headers, json={"channel": "email"}).status_code == 403
    client.post("/v1/reports", headers=customer.headers, json={"scan_id": str(customer.id)})
    assert outbox == [] and {d["reason"] for d in statuses(customer).values()} == {"test_mode"}
    assert client.get("/v1/delivery/status", headers=customer.headers).json()["email"]["available"] is False

    # the tester: codes and the report go out normally, to the tester only
    confirm(tester, "email", outbox)
    confirm(tester, "whatsapp", outbox)
    client.post("/v1/reports", headers=tester.headers, json={"scan_id": str(tester.id)})
    assert {d["channel"]: d["status"] for d in statuses(tester).values()} == {"email": "sent", "whatsapp": "accepted"}
    customer_contacts = {db.get(User, customer.user_id).email, "+447700900123"}
    assert not customer_contacts & {m["to"] for m in outbox}


# ---------- customers' WhatsApp replies are forwarded to the team ----------


def inbound(message_id, sender="919876543210", text="Is the toner OK for sensitive skin?", name="Priya"):
    return {"entry": [{"changes": [{"value": {"contacts": [{"wa_id": sender, "profile": {"name": name}}],
                                              "messages": [{"id": message_id, "from": sender, "timestamp": "1791300000",
                                                            "type": "text", "text": {"body": text}}]}}]}]}


@pytest.fixture
def team_inbox(monkeypatch, outbox):
    monkeypatch.setattr(settings, "delivery_reply_forward_email", "team@example.com")
    delivery._forwarded_ids.clear()
    yield
    delivery._forwarded_ids.clear()


def test_a_customers_whatsapp_reply_is_forwarded_to_the_team_once(db, outbox, team_inbox):
    customer = consenting_scan(db)  # registered with +919876543210
    db.get(User, customer.user_id).whatsapp_verified_at = datetime.utcnow()  # and proved it with a code
    # another account that only typed the same number (never verified it) is not named as the sender
    make_scan(db, email_prefix="same-number-unverified")
    db.query(User).filter(User.email.like("same-number-unverified-%")).update({User.name: "Not The Sender"}, synchronize_session=False)
    db.flush()
    payload = inbound("wamid.IN1")
    r = client.post("/v1/delivery/whatsapp/webhook", **signed(payload))
    assert r.status_code == 200 and r.json() == {"updated": 0, "forwarded": 1}
    mail = outbox[-1]
    assert mail["to"] == "team@example.com" and mail["subject"] == "WhatsApp message from Test (+919876543210)"
    assert "Is the toner OK for sensitive skin?" in mail["text"] and "Registered YuriWoori customer: yes" in mail["text"]
    # Meta retries the same webhook: not forwarded again
    assert client.post("/v1/delivery/whatsapp/webhook", **signed(payload)).json()["forwarded"] == 0
    assert len([m for m in outbox if m["to"] == "team@example.com"]) == 1


def test_an_unknown_number_and_media_messages_are_forwarded_without_guessing(db, outbox, team_inbox):
    payload = inbound("wamid.IN2", sender="447700900999", name="Sam")
    payload["entry"][0]["changes"][0]["value"]["messages"][0] = {"id": "wamid.IN2", "from": "447700900999", "timestamp": "x",
                                                                   "type": "image", "image": {"caption": "my skin"}}
    client.post("/v1/delivery/whatsapp/webhook", **signed(payload))
    mail = outbox[-1]
    assert mail["subject"] == "WhatsApp message from Sam (+447700900999)" and "Registered YuriWoori customer: no" in mail["text"]
    assert "[image message: my skin - media is not forwarded" in mail["text"]


def test_a_failed_forward_makes_meta_retry_and_is_then_forwarded(db, outbox, team_inbox, monkeypatch):
    original = delivery.send_email

    def down(*a, **k):
        raise delivery.DeliveryError("SMTP: OSError: connection refused")
    monkeypatch.setattr(delivery, "send_email", down)
    assert client.post("/v1/delivery/whatsapp/webhook", **signed(inbound("wamid.IN3"))).status_code == 503
    monkeypatch.setattr(delivery, "send_email", original)
    assert client.post("/v1/delivery/whatsapp/webhook", **signed(inbound("wamid.IN3"))).json()["forwarded"] == 1


def test_replies_are_not_forwarded_without_a_team_address(db, outbox, monkeypatch):
    monkeypatch.setattr(settings, "delivery_reply_forward_email", "")
    delivery._forwarded_ids.clear()
    r = client.post("/v1/delivery/whatsapp/webhook", **signed(inbound("wamid.IN4")))
    assert r.status_code == 200 and r.json()["forwarded"] == 0 and outbox == []


# ---------- Phase A: backend-triggered delivery, reports generated in memory, WhatsApp media clean-up, admin ----------


def test_after_an_analysis_the_backend_sends_the_report_to_the_verified_owner_once(db, outbox):
    scan = consenting_scan(db)
    confirm(scan, "whatsapp", outbox)
    owner = db.get(User, scan.user_id)
    before = len(outbox)
    delivery.report_after_analysis(scan.id, scan.user_id)  # what the analysis endpoint schedules
    sent = outbox[before:]
    assert sorted((m["channel"], m["to"]) for m in sent) == [("email", owner.email), ("whatsapp", owner.whatsapp)]
    delivery.report_after_analysis(scan.id, scan.user_id)  # run again (or the browser's own request): nothing twice
    assert client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)}).status_code == 200
    assert len(outbox) == before + 2
    assert db.query(Report).filter(Report.scan_id == scan.id).count() == 1


def test_the_after_analysis_task_never_sends_a_scan_to_another_customer(db, outbox):
    scan = consenting_scan(db)
    other = consenting_scan(db, email_prefix="someone-else", whatsapp="+447700900111")
    confirm(other, "whatsapp", outbox)
    before = len(outbox)
    delivery.report_after_analysis(scan.id, other.user_id)  # mismatched owner: ignored
    assert outbox[before:] == [] and db.query(Report).filter(Report.scan_id == scan.id).count() == 0


def test_an_unverified_customer_gets_nothing_until_the_code_then_it_goes_automatically(db, outbox):
    scan = consenting_scan(db)
    delivery.report_after_analysis(scan.id, scan.user_id)
    assert outbox == []
    rows = {r.channel: r for r in db.query(ResultDelivery).filter(ResultDelivery.scan_id == scan.id)}
    assert rows["whatsapp"].status == "pending" and rows["whatsapp"].error == "mobile_not_verified"
    result = confirm(scan, "whatsapp", outbox)  # the code releases the waiting report
    assert {d["channel"]: d["status"] for d in result["deliveries"]} == {"email": "sent", "whatsapp": "accepted"}


def test_no_report_content_is_stored_anywhere_it_is_generated_for_each_use(db, outbox):
    scan = consenting_scan(db)
    confirm(scan, "whatsapp", outbox)
    delivery.report_after_analysis(scan.id, scan.user_id)
    report = db.query(Report).filter(Report.scan_id == scan.id).one()
    db.refresh(report)
    assert report.content is None
    stored = json.dumps([[r.status, r.error, r.destination, r.provider_message_id]
                         for r in db.query(ResultDelivery).filter(ResultDelivery.report_id == report.id)])
    assert "Morning routine" not in stored and "hydration" not in stored.lower()
    token = reports.link_token(report.id)
    view = client.get("/v1/reports/shared", headers={"X-Report-Token": token})
    assert view.status_code == 200 and view.json()["content"]["metrics"]  # built for this request
    assert client.get("/v1/reports/shared/pdf", headers={"X-Report-Token": token}).content.startswith(b"%PDF-")
    assert client.get(f"/v1/reports/scan/{scan.id}/pdf", headers=scan.headers).content.startswith(b"%PDF-")
    db.refresh(report)
    assert report.content is None  # still nothing stored after viewing and downloading


def test_a_send_that_cannot_build_the_report_fails_safely_and_retries_later(db, outbox, monkeypatch):
    from app.services.live_catalogue import LiveCatalogueUnavailable
    scan = consenting_scan(db)
    confirm(scan, "whatsapp", outbox)
    real = reports.content_for

    def unavailable(db_, report):
        raise LiveCatalogueUnavailable("down")
    monkeypatch.setattr(reports, "content_for", unavailable)
    before = len(outbox)
    delivery.report_after_analysis(scan.id, scan.user_id)
    rows = {r.channel: r for r in db.query(ResultDelivery).filter(ResultDelivery.scan_id == scan.id)}
    assert rows["email"].status == "failed" and rows["email"].error == "catalogue_unavailable" and outbox[before:] == []
    monkeypatch.setattr(reports, "content_for", real)
    r = client.post(f"/v1/delivery/scans/{scan.id}/send", headers=scan.headers, json={"channel": "email"})
    assert r.status_code == 200 and r.json()["status"] == "sent" and len(outbox) == before + 1


@pytest.fixture
def media(monkeypatch):
    """The results template carries the PDF: uploads and deletes recorded instead of calling WhatsApp."""
    calls = {"uploaded": [], "deleted": []}
    monkeypatch.setattr(settings, "whatsapp_results_template_has_document", True)

    def upload(data, filename, mime="application/pdf"):
        calls["uploaded"].append(data[:5])
        return f"media-{len(calls['uploaded'])}"

    def delete(media_id):
        calls["deleted"].append(media_id)
        return True
    monkeypatch.setattr(delivery, "upload_whatsapp_media", upload)
    monkeypatch.setattr(delivery, "delete_whatsapp_media", delete)
    return calls


def test_the_whatsapp_pdf_is_deleted_from_whatsapp_once_delivered(db, outbox, media):
    scan = consenting_scan(db)
    confirm(scan, "whatsapp", outbox)
    delivery.report_after_analysis(scan.id, scan.user_id)
    row = db.query(ResultDelivery).filter(ResultDelivery.scan_id == scan.id, ResultDelivery.channel == "whatsapp").one()
    assert media["uploaded"] == [b"%PDF-"] and row.provider_media_id == "media-1" and media["deleted"] == []
    assert client.post("/v1/delivery/whatsapp/webhook", **signed(webhook(row.provider_message_id, "sent"))).status_code == 200
    assert media["deleted"] == []  # "sent" isn't on the phone yet
    assert client.post("/v1/delivery/whatsapp/webhook", **signed(webhook(row.provider_message_id, "delivered"))).status_code == 200
    db.refresh(row)
    assert media["deleted"] == ["media-1"] and row.provider_media_id is None and row.status == "delivered"


def test_an_uploaded_pdf_is_deleted_right_away_when_the_message_could_not_be_sent(db, outbox, media, monkeypatch):
    scan = consenting_scan(db)
    confirm(scan, "whatsapp", outbox)

    def refuse(*args, **kwargs):
        raise delivery.DeliveryError("WhatsApp: HTTP 400")
    monkeypatch.setattr(delivery, "send_whatsapp_template", refuse)
    delivery.report_after_analysis(scan.id, scan.user_id)
    row = db.query(ResultDelivery).filter(ResultDelivery.scan_id == scan.id, ResultDelivery.channel == "whatsapp").one()
    assert row.status == "failed" and media["deleted"] == ["media-1"] and row.provider_media_id is None


def test_leftover_whatsapp_uploads_are_purged_after_a_while(db, outbox, media):
    scan = consenting_scan(db)
    confirm(scan, "whatsapp", outbox)
    delivery.report_after_analysis(scan.id, scan.user_id)
    row = db.query(ResultDelivery).filter(ResultDelivery.scan_id == scan.id, ResultDelivery.channel == "whatsapp").one()
    assert delivery.purge_whatsapp_media(db)["deleted"] == 0  # recent: waits for the delivery webhook
    row.updated_at = datetime.utcnow() - timedelta(days=8)
    db.flush()
    assert delivery.purge_whatsapp_media(db) == {"due": 1, "deleted": 1}
    db.refresh(row)
    assert row.provider_media_id is None and media["deleted"] == ["media-1"]


def test_the_sheet_sync_status_is_for_admins_only_and_shows_no_contact_details(db):
    from app.core.security import ROLE_ADMIN, create_token
    from app.db.models import CustomerSheetSync
    scan = make_scan(db, email_prefix="sheet-admin")
    owner = db.get(User, scan.user_id)
    db.add(CustomerSheetSync(user_id=owner.id, status="failed", wanted_version=1, synced_version=0, attempts=2,
                             last_error="quota_RESOURCE_EXHAUSTED", next_attempt_at=datetime.utcnow()))
    db.flush()
    assert client.get("/v1/admin/customer-sheet").status_code == 401
    assert client.get("/v1/admin/customer-sheet", headers=scan.headers).status_code == 403  # a customer's session
    admin = {"Authorization": f"Bearer {create_token('admin', ROLE_ADMIN, timedelta(minutes=5))}"}
    r = client.get("/v1/admin/customer-sheet", headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False and body["by_status"].get("failed", 0) >= 1
    assert body["failed_by_error"].get("quota_RESOURCE_EXHAUSTED", 0) >= 1
    mine = next(i for i in body["items"] if i["customer_id"] == str(owner.id))
    assert mine["status"] == "failed" and mine["attempts"] == 2
    assert owner.email not in r.text and owner.whatsapp not in r.text and "Test" not in json.dumps(mine)


# ---------- report retention: existing reports preserved as they are, new reports never stored ----------


def _stored_content(db, report_id):
    from sqlalchemy import text
    return db.execute(text("select content::text from reports where id = :id"), {"id": report_id}).scalar()


def _legacy_report(db, scan):
    """A report made before the change: its content stored (inserted directly, as the old code did)."""
    from sqlalchemy import text
    report_id = uuid.uuid4()
    content = {"version": 1, "customer_name": "Old Stored Copy", "legacy_marker": "STORED-BEFORE-THE-CHANGE", "metrics": []}
    db.execute(text("insert into reports (id, scan_id, user_id, content, token_hash, created_at, expires_at) "
                    "values (:id, :scan, :user, cast(:content as jsonb), :hash, now() at time zone 'utc', "
                    "(now() at time zone 'utc') + interval '30 days')"),
               {"id": report_id, "scan": scan.id, "user": scan.user_id, "content": json.dumps(content),
                "hash": reports.token_hash(reports.link_token(report_id))})
    db.flush()
    return report_id


def test_an_existing_stored_report_stays_exactly_as_it_is_through_every_path(db, outbox, media):
    scan = consenting_scan(db)
    report_id = _legacy_report(db, scan)
    before = _stored_content(db, report_id)
    confirm(scan, "whatsapp", outbox)  # releases its deliveries: built in memory, not from the stored copy
    delivery.report_after_analysis(scan.id, scan.user_id)
    for _ in range(2):  # repeated requests
        assert client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)}).status_code == 200
    token = reports.link_token(report_id)
    served = [client.get("/v1/reports/shared", headers={"X-Report-Token": token}).text,
              client.get("/v1/reports/shared/pdf", headers={"X-Report-Token": token}).content,
              client.get(f"/v1/reports/scan/{scan.id}/pdf", headers=scan.headers).content]
    row = db.query(ResultDelivery).filter(ResultDelivery.report_id == report_id, ResultDelivery.channel == "whatsapp").one()
    assert client.post("/v1/delivery/whatsapp/webhook", **signed(webhook(row.provider_message_id, "delivered"))).status_code == 200
    assert client.post(f"/v1/delivery/scans/{scan.id}/send", headers=scan.headers, json={"channel": "email"}).status_code == 200

    assert _stored_content(db, report_id) == before  # byte-for-byte the same
    assert db.query(Report).filter(Report.scan_id == scan.id).count() == 1  # no second report beside it
    sent_text = json.dumps([m.get("text") or m.get("params") for m in outbox])
    for out in [*served, sent_text]:  # what was served and sent was generated now, never read from the stored copy
        assert (b"STORED-BEFORE-THE-CHANGE" not in out) if isinstance(out, bytes) else ("STORED-BEFORE-THE-CHANGE" not in out)
        assert (b"Old Stored Copy" not in out) if isinstance(out, bytes) else ("Old Stored Copy" not in out)


def test_new_reports_are_never_stored_by_any_path(db, outbox, media):
    scan = consenting_scan(db)
    confirm(scan, "whatsapp", outbox)
    delivery.report_after_analysis(scan.id, scan.user_id)  # automatic delivery after the analysis
    delivery.report_after_analysis(scan.id, scan.user_id)  # repeated
    report = db.query(Report).filter(Report.scan_id == scan.id).one()
    token = reports.link_token(report.id)
    for _ in range(2):
        client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)})
        client.get("/v1/reports/shared", headers={"X-Report-Token": token})
        client.get("/v1/reports/shared/pdf", headers={"X-Report-Token": token})
        client.get(f"/v1/reports/scan/{scan.id}/pdf", headers=scan.headers)
    client.post(f"/v1/delivery/scans/{scan.id}/send", headers=scan.headers, json={"channel": "email"})  # retry path
    row = db.query(ResultDelivery).filter(ResultDelivery.report_id == report.id, ResultDelivery.channel == "whatsapp").one()
    client.post("/v1/delivery/whatsapp/webhook", **signed(webhook(row.provider_message_id, "delivered")))
    assert _stored_content(db, report.id) is None
    assert len(outbox) >= 2 and media["uploaded"] and row.provider_media_id is None  # sent; PDF removed from WhatsApp


def test_the_database_layer_refuses_to_store_or_change_report_content(db):
    from app.db.models import StoredReportContent
    scan = make_scan(db, email_prefix="guard")
    db.add(Report(scan_id=scan.id, user_id=scan.user_id, content={"x": 1}, token_hash=uuid.uuid4().hex,
                  created_at=datetime.utcnow(), expires_at=datetime.utcnow()))
    with pytest.raises(StoredReportContent):
        db.flush()
    db.rollback()
    scan = make_scan(db, email_prefix="guard2")
    report_id = _legacy_report(db, scan)
    before = _stored_content(db, report_id)
    for new in ({"changed": True}, None):  # neither changing nor clearing it
        legacy = db.get(Report, report_id)
        legacy.content = new
        with pytest.raises(StoredReportContent):
            db.flush()
        db.rollback()
        scan = make_scan(db, email_prefix="guard3")
        report_id = _legacy_report(db, scan)
        before = _stored_content(db, report_id)
    legacy = db.get(Report, report_id)
    legacy.last_viewed_at = datetime.utcnow()  # its other columns can still be updated (link views, revoking)
    db.flush()
    assert _stored_content(db, report_id) == before
