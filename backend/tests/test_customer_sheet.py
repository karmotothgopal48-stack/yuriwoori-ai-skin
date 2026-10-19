"""
Customer rows in the team's Google Sheets follow-up spreadsheet (app/services/customer_sheet.py, google_sheets.py),
on the real database (rolled back). The Sheets API and Google's token endpoint are replaced by FakeSheets, an
in-memory worksheet behind httpx.MockTransport: no request leaves the machine, no real key or spreadsheet is used.
FakeSheets behaves like Sheets v4 where it matters: trailing empty cells are omitted, null cells are skipped on
write, an append answers with updates.updatedRange, an unknown tab answers 400 "Unable to parse range".
"""

import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import CustomerSheetSync, Scan, ScanStatus, User
from app.main import app
from app.services import customer_sheet, google_sheets
from app.services.customer_sheet import COLUMNS

client = TestClient(app)
SPREADSHEET = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-ab"
SA_EMAIL = "yuriwoori-sheets@yuriwoori-test.iam.gserviceaccount.com"
FAKE_KEY = "-----BEGIN PRIVATE KEY-----\nFAKE-KEY-MATERIAL-DO-NOT-LOG\n-----END PRIVATE KEY-----\n"
TOKEN = "ya29.TEST-ACCESS-TOKEN"


class FakeSheets:
    def __init__(self):
        self.tab = "CustomerTracking"
        self.header = list(COLUMNS)
        self.rows: list[list] = []  # sheet rows 2, 3, ... (padded to 13 cells)
        self.calls: list[tuple[str, str, dict]] = []
        self.failures: list[dict] = []
        self.token_status, self.token_answer = 200, {"access_token": TOKEN, "expires_in": 3599, "token_type": "Bearer"}
        self.tokens_issued = 0
        self.before_write = None  # hook: e.g. a team member sorting the sheet mid-write
        self.lose_append_answer = False
        self.append_answer_without_range = False
        self.ignore_writes = False
        self.deleted_rows = 0

    def fail(self, status, google_status="UNAVAILABLE", retry_after=None, reason=None, message="Detailed text jane@example.com", times=1):
        self.failures += [dict(status=status, google_status=google_status, retry_after=retry_after, reason=reason,
                               message=message)] * times

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            form = parse_qs(request.content.decode())
            assert form["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]
            assert form["assertion"] == ["signed-jwt-for-test"]
            self.tokens_issued += 1
            return httpx.Response(self.token_status, json=self.token_answer)
        assert request.url.host == "sheets.googleapis.com"
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        params = dict(request.url.params)
        self.calls.append((request.method, request.url.path, params))
        if self.failures:
            f = self.failures.pop(0)
            details = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": f["reason"]}] if f["reason"] else []
            headers = {"Retry-After": str(f["retry_after"])} if f["retry_after"] else {}
            return httpx.Response(f["status"], headers=headers, json={"error": {
                "code": f["status"], "message": f["message"], "status": f["google_status"], "details": details}})
        return self._apply(request, params)

    def _cells(self, a1: str):
        m = re.fullmatch(r"'((?:[^']|'')+)'!([A-Z]+)(\d*):([A-Z]+)(\d*)", a1)
        assert m, a1
        if m.group(1).replace("''", "'") != self.tab:
            return None
        return (int(m.group(3)) if m.group(3) else None), (int(m.group(5)) if m.group(5) else None)

    def _sheet(self):
        return ([self.header] if self.header else []) + self.rows

    @staticmethod
    def _trim(row):
        row = list(row)
        while row and row[-1] == "":
            row.pop()
        return row

    def _apply(self, request, params):
        path = request.url.path
        if path == f"/v4/spreadsheets/{SPREADSHEET}":
            return httpx.Response(200, json={"properties": {"title": "YuriWoori Customer Tracking"},
                                             "sheets": [{"properties": {"title": self.tab, "sheetId": 0}}]})
        if path == f"/v4/spreadsheets/{SPREADSHEET}:batchUpdate":
            for req in json.loads(request.content)["requests"]:
                if "updateSheetProperties" in req and "title" in req["updateSheetProperties"]["properties"]:
                    self.tab = req["updateSheetProperties"]["properties"]["title"]
                elif "deleteDimension" in req:
                    r = req["deleteDimension"]["range"]
                    assert r["dimension"] == "ROWS" and r["endIndex"] - r["startIndex"] == 1
                    del self.rows[r["startIndex"] - 1]
                    self.deleted_rows += 1
            return httpx.Response(200, json={"replies": []})
        prefix = f"/v4/spreadsheets/{SPREADSHEET}/values/"
        assert path.startswith(prefix), path
        a1 = path[len(prefix):]
        append = a1.endswith(":append")
        a1 = a1[:-len(":append")] if append else a1
        cells = self._cells(a1)
        if cells is None:
            return httpx.Response(400, json={"error": {"code": 400, "message": f"Unable to parse range: {a1}", "status": "INVALID_ARGUMENT"}})
        first, last = cells
        if request.method == "GET":
            sheet = self._sheet()
            rows = sheet if first is None else sheet[first - 1:last]
            rows = [self._trim(r) for r in rows]
            while rows and not rows[-1]:
                rows.pop()
            return httpx.Response(200, json={"range": a1, "majorDimension": "ROWS", **({"values": rows} if rows else {})})
        body = json.loads(request.content)
        assert params.get("valueInputOption") == "RAW"
        if self.before_write:
            self.before_write(self)
        if request.method == "PUT" and first == 1:
            self.header = list(body["values"][0])
            return httpx.Response(200, json={"updatedRange": a1, "updatedCells": 13})
        if request.method == "PUT":
            row = self.rows[first - 2]
            if not self.ignore_writes:
                for i, value in enumerate(body["values"][0]):
                    if value is not None:  # Sheets skips nulls
                        row[i] = value
            return httpx.Response(200, json={"updatedRange": a1, "updatedCells": 11})
        if request.method == "POST" and append:
            assert params.get("insertDataOption") == "INSERT_ROWS"
            self.rows.append([("" if v is None else v) for v in body["values"][0]])
            n = len(self.rows) + 1
            if self.lose_append_answer:
                raise httpx.ReadTimeout("read timed out", request=request)
            updates = {} if self.append_answer_without_range else {"updatedRange": f"{self.tab}!A{n}:M{n}"}
            return httpx.Response(200, json={"spreadsheetId": SPREADSHEET, "updates": updates})
        raise AssertionError(f"unexpected call {request.method} {path}")

    def row_of(self, customer_id) -> dict:
        found = [r for r in self.rows if r[0] == str(customer_id)]
        assert len(found) == 1, f"{len(found)} rows for this customer"
        return dict(zip(COLUMNS, found[0]))

    def writes(self):
        return [c for c in self.calls if c[0] in ("PUT", "POST")]


@pytest.fixture
def background(monkeypatch):
    """Background runs are recorded instead of run (they would open their own database session)."""
    runs = []
    monkeypatch.setattr(customer_sheet, "run_in_background", lambda: runs.append(1))
    return runs


@pytest.fixture
def key_file(tmp_path):
    path = tmp_path / "yuriwoori-sheets-key.json"  # outside the project folder
    path.write_text(json.dumps({"type": "service_account", "project_id": "yuriwoori-test", "private_key_id": "k1",
                                "private_key": FAKE_KEY, "client_email": SA_EMAIL, "token_uri": "https://oauth2.googleapis.com/token"}))
    return path


@pytest.fixture
def sheets(monkeypatch, background, key_file):
    fake = FakeSheets()
    for key, value in (("customer_sheet_sync_enabled", True), ("google_sheets_spreadsheet_id", SPREADSHEET),
                       ("google_sheets_worksheet_name", "CustomerTracking"), ("google_service_account_file", str(key_file))):
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(google_sheets, "google_auth_available", lambda: True)
    monkeypatch.setattr(google_sheets, "_signed_assertion", lambda info: "signed-jwt-for-test")
    monkeypatch.setattr(google_sheets, "client", lambda: httpx.Client(transport=httpx.MockTransport(fake.handle)))
    google_sheets.reset_token()
    return fake


VERIFIED = datetime(2026, 10, 19, 9, 35)


def customer(db, *, name="Priya Sharma", whatsapp="+919876543210", version="2026-10-19c", whatsapp_verified_at=VERIFIED,
             **fields) -> User:
    """An eligible customer by default: consent to the current notice and a verified WhatsApp number."""
    user = User(email=f"sheet-test-{uuid.uuid4().hex}@example.com", name=name, whatsapp=whatsapp,
                consented_at=datetime(2026, 10, 19, 9, 30), consent_version=version,
                whatsapp_verified_at=whatsapp_verified_at, **fields)
    db.add(user)
    db.flush()
    return user


def queued(db, user) -> CustomerSheetSync:
    customer_sheet.mark_changed(db, user)
    db.commit()
    return db.get(CustomerSheetSync, user.id)


def make_due(db, job):
    job.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()


def failed_with(db, job, code):
    db.refresh(job)
    assert (job.status, job.last_error) == ("failed", code), (job.status, job.last_error)
    return job


# ---------- submission and the exported values ----------


@pytest.fixture
def whatsapp_otp(monkeypatch):
    """WhatsApp configured, with the sender replaced by a list: one-time codes are read from it, nothing is sent."""
    from app.services import delivery
    sent = []
    for key, value in (("whatsapp_access_token", "t"), ("whatsapp_phone_number_id", "1"), ("whatsapp_otp_template", "otp"),
                       ("whatsapp_results_template", "results"), ("delivery_test_mode", False)):
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(delivery, "send_whatsapp_template", lambda to, template, params, **kw: sent.append((to, params[0])) or "wamid.x")
    return sent


def verify_whatsapp(headers, sent):
    assert client.post("/v1/delivery/verify/start", headers=headers, json={"channel": "whatsapp"}).status_code == 200
    r = client.post("/v1/delivery/verify/confirm", headers=headers, json={"channel": "whatsapp", "code": sent[-1][1]})
    assert r.status_code == 200, r.text


def signup(body):
    r = client.post("/v1/users/signup", json=body)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_a_signup_alone_is_not_synced_the_row_follows_whatsapp_verification(db, sheets, background, whatsapp_otp):
    email = f"sheet-signup-{uuid.uuid4().hex}@example.com"
    headers = signup({"name": "Asha Rao", "whatsapp": "98765 43210", "email": email, "consent": True})
    user = db.query(User).filter(User.email == email).one()
    assert user.consent_version == "2026-10-19c"
    assert db.get(CustomerSheetSync, user.id) is None  # consent alone: not eligible

    verify_whatsapp(headers, whatsapp_otp)
    job = db.get(CustomerSheetSync, user.id)
    assert (job.status, job.wanted_version, job.synced_version) == ("pending", 1, 0)
    assert sheets.calls == [] and sheets.tokens_issued == 0  # Google is never called inside the customer's request
    assert background[-1] == 1  # the write runs after the response
    assert customer_sheet.process_due(db)["synced"] == 1
    assert sheets.row_of(user.id)["Phone Verification Status"].startswith("Verified ")


def test_a_wrong_code_does_not_make_a_customer_eligible(db, sheets, whatsapp_otp):
    email = f"sheet-wrong-{uuid.uuid4().hex}@example.com"
    headers = signup({"name": "Asha", "whatsapp": "98765 43210", "email": email, "consent": True})
    assert client.post("/v1/delivery/verify/start", headers=headers, json={"channel": "whatsapp"}).status_code == 200
    wrong = "000000" if whatsapp_otp[-1][1] != "000000" else "111111"
    assert client.post("/v1/delivery/verify/confirm", headers=headers, json={"channel": "whatsapp", "code": wrong}).status_code == 400
    assert db.get(CustomerSheetSync, db.query(User).filter(User.email == email).one().id) is None


@pytest.fixture
def email_outbox(monkeypatch):
    """Email configured with the provider replaced by a list (sign-in codes are read from it; nothing is sent)."""
    from app.services import delivery
    sent = []
    for key, value in (("smtp_host", "smtp.example.com"), ("smtp_from", "YuriWoori <care@example.com>"),
                       ("delivery_test_mode", False)):
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(delivery, "send_email", lambda to, subject, text, **kw: sent.append(text) or "<id@example.com>")
    return sent


def test_a_returning_customer_who_signs_in_with_the_emailed_code_updates_their_one_row(db, sheets, background, email_outbox,
                                                                                       whatsapp_otp):
    email = f"sheet-login-{uuid.uuid4().hex}@example.com"
    body = {"name": "Asha Rao", "whatsapp": "98765 43210", "email": email, "consent": True}
    verify_whatsapp(signup(body), whatsapp_otp)  # first visit: signup + WhatsApp code
    user = db.query(User).filter(User.email == email).one()
    customer_sheet.process_due(db)
    assert sheets.row_of(user.id)["Email Verification Status"] == "Not verified"

    # another device: the code step itself queues nothing (not signed in yet), nor does a wrong code
    login = {**body, "name": "Asha R"}
    r = client.post("/v1/users/signup", json=login)
    assert r.json()["code_required"]
    code = re.search(r"\d{6}", email_outbox[-1]).group(0)
    assert client.post("/v1/users/signup", json={**login, "code": "000000" if code != "000000" else "111111"}).status_code == 400
    job = db.get(CustomerSheetSync, user.id)
    db.refresh(job)
    assert (job.status, job.wanted_version) == ("synced", 1)

    # the successful sign-in queues an update; the same row changes, no second row
    r = client.post("/v1/users/signup", json={**login, "code": code})
    assert r.status_code == 200 and r.json()["user"]["id"] == str(user.id)
    db.refresh(job)
    assert (job.status, job.wanted_version) == ("pending", 2)
    assert len(background) == 3  # background writes after the signup, the WhatsApp code and the sign-in
    assert customer_sheet.process_due(db)["synced"] == 1
    row = sheets.row_of(user.id)
    assert row["Customer Name"] == "Asha R"
    assert row["Email Verification Status"].startswith("Verified ")  # the emailed code proved the address
    assert len(sheets.rows) == 1
    assert code not in json.dumps(sheets.rows) and r.json()["token"] not in json.dumps(sheets.rows)  # no code or token


def test_a_new_number_waits_for_its_own_code_and_restoring_a_session_does_not_sync(db, sheets, background, whatsapp_otp):
    email = f"sheet-again-{uuid.uuid4().hex}@example.com"
    headers = signup({"name": "Ravi", "whatsapp": "98765 43210", "email": email, "consent": True})
    verify_whatsapp(headers, whatsapp_otp)
    user = db.query(User).filter(User.email == email).one()
    customer_sheet.process_due(db)

    assert client.get("/v1/users/me", headers=headers).status_code == 200  # a page load with the saved session
    job = db.get(CustomerSheetSync, user.id)
    db.refresh(job)
    assert (job.status, job.wanted_version) == ("synced", 1)  # nothing re-queued

    # same browser, a different number: it isn't verified, so the sheet keeps the last verified details
    r = client.post("/v1/users/signup", headers=headers, json={"name": "Ravi", "whatsapp": "91234 56789", "email": email,
                                                               "consent": True, "report_consent": True})
    assert r.status_code == 200
    db.refresh(job)
    assert job.wanted_version == 1
    assert sheets.row_of(user.id)["Phone / WhatsApp Number"] == "+919876543210"

    from app.db.models import ContactVerification
    for v in db.query(ContactVerification).filter(ContactVerification.user_id == user.id).all():
        v.created_at -= timedelta(minutes=2)  # past the 60-second wait between codes
    db.flush()
    verify_whatsapp(headers, whatsapp_otp)  # the code for the new number
    assert whatsapp_otp[-1][0] == "+919123456789"
    customer_sheet.process_due(db)
    row = sheets.row_of(user.id)
    assert row["Phone / WhatsApp Number"] == "+919123456789" and "report sending agreed" in row["Consent Status"]
    assert len(sheets.rows) == 1


def test_signup_validation_is_unchanged_and_queues_nothing_when_refused(db, sheets):
    before = db.query(CustomerSheetSync).count()
    assert client.post("/v1/users/signup", json={"name": "A", "whatsapp": "98765 43210", "email": "x@example.com",
                                                 "consent": False}).status_code == 400
    assert client.post("/v1/users/signup", json={"name": "A", "whatsapp": "12", "email": "y@example.com",
                                                 "consent": True}).status_code == 422
    assert db.query(CustomerSheetSync).count() == before


def test_the_row_holds_only_real_statuses_from_the_database(db):
    user = customer(db, whatsapp_verified_at=None)
    values = dict(zip(COLUMNS, customer_sheet.row_values(db, user, datetime(2026, 10, 19, 10, 0))))
    assert values["Customer ID"] == str(user.id)
    assert values["Consent Status"] == "Privacy notice accepted 2026-10-19 09:30 UTC (version 2026-10-19c); report sending not agreed"
    assert values["Email Verification Status"] == values["Phone Verification Status"] == "Not verified"
    assert values["Analysis Status"] == "Not started"
    assert values["Phone / WhatsApp Number"] == "+919876543210"  # written RAW, so it stays text
    assert values["Last Updated"] == "2026-10-19 10:00 UTC"
    assert all(values[c] is None for c in customer_sheet.TEAM_COLUMNS)  # the team's columns are never written

    user.email_verified_at = datetime(2026, 10, 19, 9, 40)
    user.whatsapp_verified_at = datetime(2026, 10, 19, 9, 41)
    user.report_consent_at = datetime(2026, 10, 19, 9, 31)
    db.add(Scan(user_id=user.id, status=ScanStatus.analyzed, angles_captured=["front"]))
    db.flush()
    values = dict(zip(COLUMNS, customer_sheet.row_values(db, user, datetime(2026, 10, 19, 10, 0))))
    assert values["Consent Status"].endswith("; report sending agreed 2026-10-19 09:31 UTC")
    assert values["Email Verification Status"] == "Verified 2026-10-19 09:40 UTC"
    assert values["Phone Verification Status"] == "Verified 2026-10-19 09:41 UTC"
    assert values["Analysis Status"] == "Analysed (1 scan)"
    assert len(values) == 13  # no photo, image data, measurements, report content, codes or tokens


@pytest.mark.parametrize("version", ["2026-10-13b", "2026-10-19", "2026-10-19b"])  # notices before the current one
def test_customers_who_accepted_an_earlier_notice_are_not_queued(db, version):
    user = customer(db, version=version)
    customer_sheet.mark_changed(db, user)
    db.flush()
    assert db.get(CustomerSheetSync, user.id) is None


@pytest.mark.parametrize("fields", [{"whatsapp_verified_at": None}, {"whatsapp": None}, {"consented_at": None}])
def test_without_valid_consent_and_a_verified_whatsapp_number_nobody_is_queued(db, fields):
    user = customer(db)
    for key, value in fields.items():
        setattr(user, key, value)
    customer_sheet.mark_changed(db, user)
    db.flush()
    assert db.get(CustomerSheetSync, user.id) is None
    assert customer_sheet.eligible(customer(db)) is True


# ---------- writing to Google Sheets ----------


def test_a_queued_customer_is_appended_once_and_synced_only_after_reading_it_back(db, sheets):
    user = customer(db, name='=HYPERLINK("http://x","click")')
    job = queued(db, user)
    assert customer_sheet.process_due(db) == {"synced": 1, "failed": 0, "not_eligible": 0}
    row = sheets.row_of(user.id)
    assert row["Customer Name"] == '=HYPERLINK("http://x","click")'  # RAW: stored as text, never run
    assert row["Email"] == user.email and row["Phone / WhatsApp Number"] == "+919876543210"
    assert row["Assigned Team Member"] == row["Follow-up Status"] == row["Follow-up Notes"] == ""
    methods = [c[0] for c in sheets.calls]
    assert methods == ["GET", "POST", "GET"]  # look up, append, read the row back
    assert sheets.calls[-1][1].endswith("A2:M2")
    db.refresh(job)
    assert (job.status, job.synced_version, job.attempts, job.last_error) == ("synced", 1, 0, None)
    assert job.last_synced_at is not None


def test_an_update_changes_the_same_row_and_keeps_the_teams_follow_up(db, sheets):
    user = customer(db)
    queued(db, user)
    customer_sheet.process_due(db)
    sheets.rows[0][9:12] = ["Meera", "Called - interested", "Prefers evening calls"]

    user.whatsapp_verified_at = datetime(2026, 10, 19, 11, 0)
    job = queued(db, user)
    assert customer_sheet.process_due(db)["synced"] == 1
    row = sheets.row_of(user.id)  # still exactly one row
    assert row["Phone Verification Status"] == "Verified 2026-10-19 11:00 UTC"
    assert (row["Assigned Team Member"], row["Follow-up Status"], row["Follow-up Notes"]) == \
           ("Meera", "Called - interested", "Prefers evening calls")
    put = [c for c in sheets.writes() if c[0] == "PUT"]
    assert len(put) == 1 and put[0][1].endswith("A2:M2")
    db.refresh(job)
    assert (job.status, job.synced_version, job.wanted_version) == ("synced", 2, 2)


def test_an_append_whose_answer_was_lost_is_found_and_not_added_twice(db, sheets):
    user = customer(db)
    job = queued(db, user)
    sheets.lose_append_answer = True
    customer_sheet.process_due(db)
    failed_with(db, job, "timeout")
    assert len(sheets.rows) == 1  # Google did append it

    sheets.lose_append_answer = False
    make_due(db, job)
    assert customer_sheet.process_due(db)["synced"] == 1
    sheets.row_of(user.id)  # still one row: the retry found it by Customer ID and updated it
    assert [c[0] for c in sheets.writes()] == ["POST", "PUT"]


def test_an_append_answer_without_its_range_is_not_counted_as_written(db, sheets):
    user = customer(db)
    job = queued(db, user)
    sheets.append_answer_without_range = True
    customer_sheet.process_due(db)
    failed_with(db, job, "write_not_confirmed")
    sheets.append_answer_without_range = False
    make_due(db, job)
    customer_sheet.process_due(db)
    sheets.row_of(user.id)
    db.refresh(job)
    assert job.status == "synced"


def test_a_write_google_did_not_apply_is_never_marked_synced(db, sheets):
    user = customer(db)
    queued(db, user)
    customer_sheet.process_due(db)
    sheets.ignore_writes = True
    user.email_verified_at = datetime(2026, 10, 19, 12, 0)
    job = queued(db, user)
    customer_sheet.process_due(db)
    failed_with(db, job, "write_not_confirmed")
    assert job.synced_version == 1  # the new version isn't claimed as written


def test_a_google_outage_keeps_the_customer_queued_and_a_later_retry_writes_it(db, sheets):
    user = customer(db)
    job = queued(db, user)
    sheets.fail(503, "UNAVAILABLE", retry_after=120)
    assert customer_sheet.process_due(db) == {"synced": 0, "failed": 1, "not_eligible": 0}
    failed_with(db, job, "http_503_UNAVAILABLE")
    assert job.attempts == 1 and job.next_attempt_at >= datetime.utcnow() + timedelta(seconds=110)
    assert sheets.rows == []
    assert customer_sheet.process_due(db) == {"synced": 0, "failed": 0, "not_eligible": 0}  # not due yet

    make_due(db, job)
    assert customer_sheet.process_due(db)["synced"] == 1
    db.refresh(job)
    assert job.status == "synced" and job.attempts == 0 and job.last_error is None
    sheets.row_of(user.id)


def test_quota_limits_wait_for_retry_after_or_back_off(db, sheets):
    job = queued(db, customer(db))
    sheets.fail(429, "RESOURCE_EXHAUSTED", retry_after=900)
    customer_sheet.process_due(db)
    failed_with(db, job, "quota_RESOURCE_EXHAUSTED")
    assert job.next_attempt_at >= datetime.utcnow() + timedelta(seconds=890)

    make_due(db, job)
    sheets.fail(403, "PERMISSION_DENIED", reason="RATE_LIMIT_EXCEEDED")  # per-user quota is a 403 with this reason
    customer_sheet.process_due(db)
    failed_with(db, job, "quota_PERMISSION_DENIED")
    assert job.next_attempt_at < datetime.utcnow() + timedelta(minutes=30)  # transient, short backoff


@pytest.mark.parametrize("status,google_status,reason,message,code", [
    (403, "PERMISSION_DENIED", None, "The caller does not have permission", "forbidden_PERMISSION_DENIED"),  # not shared
    (404, "NOT_FOUND", None, "Requested entity was not found.", "not_found_NOT_FOUND"),  # wrong spreadsheet ID
    (403, "PERMISSION_DENIED", "SERVICE_DISABLED", "Google Sheets API has not been used", "sheets_api_not_enabled"),
])
def test_missing_access_is_reported_and_retried_hourly(db, sheets, status, google_status, reason, message, code):
    job = queued(db, customer(db))
    sheets.fail(status, google_status, reason=reason, message=message)
    customer_sheet.process_due(db)
    failed_with(db, job, code)
    assert job.next_attempt_at >= datetime.utcnow() + timedelta(minutes=59) and sheets.rows == []


def test_a_missing_worksheet_tab_is_reported(db, sheets, monkeypatch):
    monkeypatch.setattr(settings, "google_sheets_worksheet_name", "Customers")
    job = queued(db, customer(db))
    customer_sheet.process_due(db)
    failed_with(db, job, "worksheet_not_found")


def test_a_rejected_service_account_key_is_reported_not_retried_in_a_loop(db, sheets):
    sheets.token_status, sheets.token_answer = 400, {"error": "invalid_grant", "error_description": "Invalid JWT Signature."}
    job = queued(db, customer(db))
    customer_sheet.process_due(db)
    failed_with(db, job, "auth_invalid_grant")
    assert job.next_attempt_at >= datetime.utcnow() + timedelta(minutes=59)
    assert sheets.calls == []


def test_the_access_token_is_reused_and_renewed_once_after_a_401(db, sheets):
    queued(db, customer(db))
    queued(db, customer(db, name="Second"))
    customer_sheet.process_due(db)
    assert sheets.tokens_issued == 1  # one token for both customers (kept in memory only)
    sheets.fail(401, "UNAUTHENTICATED")
    queued(db, customer(db, name="Third"))
    assert customer_sheet.process_due(db)["synced"] == 1
    assert sheets.tokens_issued == 2


def test_two_rows_with_the_same_customer_id_are_left_for_the_team(db, sheets):
    user = customer(db)
    sheets.rows = [[str(user.id)] + [""] * 12, [str(user.id)] + [""] * 12]
    job = queued(db, user)
    customer_sheet.process_due(db)
    failed_with(db, job, "duplicate_customer_rows")
    assert sheets.writes() == []


def test_a_sheet_with_other_columns_is_not_written(db, sheets):
    sheets.header = list(COLUMNS[:-1]) + ["Updated"]
    job = queued(db, customer(db))
    customer_sheet.process_due(db)
    failed_with(db, job, "worksheet_columns_mismatch")
    assert sheets.writes() == [] and job.next_attempt_at >= datetime.utcnow() + timedelta(minutes=59)


def test_a_row_moved_by_sorting_mid_write_is_detected_and_both_customers_are_repaired(db, sheets):
    first, second = customer(db, name="First"), customer(db, name="Second")
    queued(db, first)
    queued(db, second)
    customer_sheet.process_due(db)
    sheets.before_write = lambda fake: fake.rows.reverse()  # a team member sorts between lookup and write
    first.email_verified_at = datetime(2026, 10, 19, 12, 0)
    job = queued(db, first)
    customer_sheet.process_due(db)
    failed_with(db, job, "row_moved")
    assert db.get(CustomerSheetSync, second.id).status == "pending"  # the overwritten row is queued for repair

    sheets.before_write = None
    make_due(db, job)
    customer_sheet.process_due(db)
    assert sheets.row_of(first.id)["Customer Name"] == "First" and sheets.row_of(second.id)["Customer Name"] == "Second"
    assert sheets.row_of(first.id)["Email Verification Status"] == "Verified 2026-10-19 12:00 UTC"


# ---------- configuration ----------


def test_missing_settings_are_named_without_their_values_and_nothing_is_sent(db, sheets, monkeypatch):
    monkeypatch.setattr(settings, "google_sheets_spreadsheet_id", "")
    monkeypatch.setattr(settings, "google_service_account_file", "")
    monkeypatch.setattr(settings, "google_sheets_worksheet_name", "Bad:Name")
    problems = " | ".join(google_sheets.config_problems())
    for name in ("GOOGLE_SHEETS_SPREADSHEET_ID", "GOOGLE_SERVICE_ACCOUNT_FILE", "GOOGLE_SHEETS_WORKSHEET_NAME"):
        assert name in problems
    job = queued(db, customer(db))
    assert customer_sheet.process_due(db) == {"skipped": "not_configured"}
    db.refresh(job)
    assert job.status == "pending"
    checks = customer_sheet.connection_test()
    assert len(checks) == 1 and checks[0][1] is False
    assert sheets.calls == [] and sheets.tokens_issued == 0


def test_a_key_file_inside_the_project_or_not_a_service_account_key_is_refused(sheets, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "google_service_account_file", str(google_sheets.PROJECT_DIR / "backend" / "key.json"))
    assert any("inside the project folder" in p for p in google_sheets.config_problems())
    other = tmp_path / "oauth-client.json"
    other.write_text(json.dumps({"installed": {"client_id": "x"}}))
    monkeypatch.setattr(settings, "google_service_account_file", str(other))
    assert "GOOGLE_SERVICE_ACCOUNT_FILE: credentials_not_a_service_account_key" in google_sheets.config_problems()
    monkeypatch.setattr(settings, "google_service_account_file", str(tmp_path / "missing.json"))
    assert "GOOGLE_SERVICE_ACCOUNT_FILE does not point to a file" in google_sheets.config_problems()


def test_without_the_google_auth_package_it_says_so_and_stays_queued(db, sheets, monkeypatch):
    monkeypatch.setattr(google_sheets, "google_auth_available", lambda: False)
    assert any("google-auth" in p for p in google_sheets.config_problems())
    job = queued(db, customer(db))
    assert customer_sheet.process_due(db) == {"skipped": "not_configured"}
    db.refresh(job)
    assert job.status == "pending"


def test_sync_disabled_queues_but_writes_nothing(db, sheets, monkeypatch):
    monkeypatch.setattr(settings, "customer_sheet_sync_enabled", False)
    job = queued(db, customer(db))
    assert customer_sheet.process_due(db) == {"skipped": "disabled"}
    db.refresh(job)
    assert job.status == "pending" and sheets.calls == []


def test_the_service_account_email_is_shown_for_sharing_but_never_the_key(sheets):
    assert google_sheets.service_account_email() == SA_EMAIL


def test_the_connection_test_reads_only(sheets):
    checks = customer_sheet.connection_test()
    assert all(ok for _, ok, _ in checks), checks
    assert [name for name, _, _ in checks] == ["settings", "service account", "spreadsheet", "worksheet", "columns"]
    assert "YuriWoori Customer Tracking" in checks[2][2]
    assert sheets.writes() == []


def test_the_dummy_write_uses_one_fake_row_and_no_database_record(db, sheets):
    before = (db.query(User).count(), db.query(CustomerSheetSync).count())
    lines = customer_sheet.dummy_write()
    assert lines[0] == "first write: added" and lines[1] == "second write: updated" and lines[2].endswith(": 1")
    assert len(sheets.rows) == 1 and sheets.rows[0][0].startswith("TEST-")
    assert sheets.rows[0][3] == "dummy.customer@example.com"
    assert (db.query(User).count(), db.query(CustomerSheetSync).count()) == before


def test_the_jwt_is_signed_with_google_auth_and_verifies(key_file):
    """The real signing path (google-auth), with a throwaway key generated here; nothing is sent anywhere."""
    pytest.importorskip("google.auth.crypt")
    import base64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
    info = {**json.loads(key_file.read_text()), "private_key": pem}
    token = google_sheets._signed_assertion(info)
    header_b64, claims_b64, signature_b64 = token.split(".")
    pad = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))  # noqa: E731
    claims = json.loads(pad(claims_b64))
    assert json.loads(pad(header_b64))["alg"] == "RS256"
    assert claims["iss"] == SA_EMAIL and claims["aud"] == google_sheets.TOKEN_URI and claims["scope"] == google_sheets.SCOPE
    assert claims["exp"] - claims["iat"] == 3600
    private.public_key().verify(pad(signature_b64), f"{header_b64}.{claims_b64}".encode(), padding.PKCS1v15(), hashes.SHA256())


def test_setup_names_the_empty_tab_and_writes_the_headers(sheets):
    sheets.tab, sheets.header = "Sheet1", []
    lines = customer_sheet.setup_worksheet()
    assert lines == ["renamed the only tab 'Sheet1' to 'CustomerTracking'", "wrote the 13 column headers in row 1 and froze it"]
    assert sheets.tab == "CustomerTracking" and sheets.header == list(COLUMNS)
    assert customer_sheet.setup_worksheet() == ["row 1 already holds the 13 columns"]  # safe to run again


def test_setup_refuses_a_tab_that_holds_anything(sheets):
    sheets.tab, sheets.header = "Sheet1", ["Name", "Phone"]
    with pytest.raises(google_sheets.SheetsError, match="setup_refused_tab_not_empty"):
        customer_sheet.setup_worksheet()
    assert sheets.tab == "Sheet1" and sheets.header == ["Name", "Phone"]


def test_the_dummy_cleanup_deletes_only_its_own_test_row(db, sheets):
    user = customer(db)
    queued(db, user)
    customer_sheet.process_due(db)
    sheets.rows[0][9:12] = ["Meera", "Called", "note"]
    lines = customer_sheet.dummy_write(cleanup=True)
    assert lines[3].startswith("deleted test row 3;") and lines[4] == "data rows before: 1, after: 1"
    assert sheets.deleted_rows == 1
    assert sheets.row_of(user.id)["Follow-up Notes"] == "note"  # the customer's row is untouched
    with pytest.raises(google_sheets.SheetsError, match="cleanup_refused_not_a_test_row"):
        with google_sheets.client() as h:
            customer_sheet._delete_test_row(h, str(user.id))


# ---------- retries, reconciling, logs ----------


def test_retry_failed_makes_failures_due_now(db, sheets):
    job = queued(db, customer(db))
    sheets.fail(503, retry_after=3600)
    customer_sheet.process_due(db)
    assert customer_sheet.retry_failed(db) >= 1
    assert customer_sheet.process_due(db)["synced"] >= 1
    db.refresh(job)
    assert job.status == "synced"


def test_reconcile_is_a_dry_run_unless_applied(db, sheets):
    user = customer(db)  # signed up while nothing queued them
    result = customer_sheet.reconcile(db)
    assert result["not_queued"] >= 1 and result["queued_now"] == 0
    assert db.get(CustomerSheetSync, user.id) is None and sheets.calls == []
    customer_sheet.reconcile(db, apply=True)
    assert db.get(CustomerSheetSync, user.id).status == "pending"


def test_logs_and_stored_errors_never_hold_personal_data_keys_or_tokens(db, sheets, caplog, whatsapp_otp):
    caplog.set_level(logging.DEBUG)
    email = f"sheet-logs-{uuid.uuid4().hex}@example.com"
    verify_whatsapp(signup({"name": "Kavya Logcheck", "whatsapp": "91234 56789", "email": email, "consent": True}), whatsapp_otp)
    user = db.query(User).filter(User.email == email).one()
    sheets.fail(500, "INTERNAL")
    customer_sheet.process_due(db)
    job = db.get(CustomerSheetSync, user.id)
    make_due(db, job)
    customer_sheet.process_due(db)
    assert db.get(CustomerSheetSync, user.id).status == "synced"
    stored = " ".join(str(j.last_error) for j in db.query(CustomerSheetSync).all())
    for secret in (email, "Kavya", "Logcheck", "9123456789", "jane@example.com", "Detailed text", TOKEN,
                   "FAKE-KEY-MATERIAL", "signed-jwt-for-test", "PRIVATE KEY", whatsapp_otp[-1][1]):
        assert secret not in caplog.text, secret
        assert secret not in stored, secret
    assert str(user.id) in caplog.text  # the customer is identified by internal ID only
