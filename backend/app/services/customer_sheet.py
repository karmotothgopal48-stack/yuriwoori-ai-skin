"""Customer rows in the team's follow-up spreadsheet ("YuriWoori Customer Tracking", worksheet CustomerTracking) in
Google Sheets, through the Sheets API v4 as a service account (app/services/google_sheets.py).

PostgreSQL stays the source of truth. A customer change (signup, a confirmed contact, a finished analysis) only
queues their customer_sheet_sync row in the same database transaction (mark_changed); after the response a
background run writes due rows (run_in_background), and scripts/customer_sheet.py retries, reconciles and checks.
So a Google outage never loses a submission or slows/breaks the skin analysis.

Idempotent by the internal customer ID (users.id) in the "Customer ID" column, never by email: every write first
looks the ID up, so an append whose answer was lost is found and updated, not added twice. A row is marked synced
only after reading it back from Google and seeing the values that were written. Updates leave the team's columns
(Assigned Team Member, Follow-up Status, Follow-up Notes) untouched: Sheets skips null cells in a write. Values are
written RAW, so text is never run as a formula and "+91..." stays text.

Exported: name, email, WhatsApp number, consent, verification and analysis statuses with their dates - all read
from the database, nothing inferred. Never photos, image data, measurements, report content, codes or tokens.
Only customers who accepted a privacy notice that names the spreadsheet (TRACKER_NOTICE_FROM or later) AND verified
their WhatsApp number with the one-time code are queued: the row appears when the code is confirmed.

Rollback to the earlier Microsoft Excel Online version: README "Customer follow-up spreadsheet" > Rollback."""

import logging
import re
import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CustomerSheetSync, Scan, ScanStatus, User
from app.services import google_sheets
from app.services.google_sheets import SheetsError

logger = logging.getLogger(__name__)

COLUMNS = ("Customer ID", "Date Added", "Customer Name", "Email", "Phone / WhatsApp Number", "Consent Status",
           "Email Verification Status", "Phone Verification Status", "Analysis Status", "Assigned Team Member",
           "Follow-up Status", "Follow-up Notes", "Last Updated")
TEAM_COLUMNS = ("Assigned Team Member", "Follow-up Status", "Follow-up Notes")  # filled by the team, never written
LAST_COLUMN = "M"  # COLUMNS span A:M
# First privacy-notice version (endpoints/users.py CONSENT_VERSION) that tells customers about the Google spreadsheet
# (and that it follows WhatsApp verification).
TRACKER_NOTICE_FROM = "2026-10-19c"
STALE_CLAIM = timedelta(minutes=10)
MAX_BACKOFF = timedelta(hours=6)
PERMANENT_BACKOFF = timedelta(hours=1)  # bad key, sheet not shared, wrong columns: retried, but not hammered


def eligible(user: User) -> bool:
    """Valid consent to the notice that names the sheet, and a WhatsApp number verified with the one-time code."""
    return bool(user.consented_at and user.consent_version and user.consent_version >= TRACKER_NOTICE_FROM
                and user.whatsapp and user.whatsapp_verified_at)


def ready() -> bool:
    return settings.customer_sheet_sync_enabled and not google_sheets.config_problems()


def mark_changed(db: Session, user: User) -> None:
    """Queue this customer's row for writing, inside the caller's transaction (the caller commits)."""
    if not eligible(user):
        return
    if user.id is None:
        db.flush()  # a new user gets its id
    now = datetime.utcnow()
    job = db.get(CustomerSheetSync, user.id)
    if job is None:
        db.add(CustomerSheetSync(user_id=user.id, status="pending", wanted_version=1, synced_version=0, attempts=0,
                                 next_attempt_at=now, created_at=now))
        return
    job.wanted_version = CustomerSheetSync.wanted_version + 1  # atomic in SQL; a running write sees it's outdated
    job.next_attempt_at = now
    job.attempts = 0
    job.updated_at = now
    if job.status != "syncing":
        job.status = "pending"


# ---------- the row ----------


def _when(moment: datetime | None) -> str:
    return moment.strftime("%Y-%m-%d %H:%M UTC") if moment else ""


def _analysis_status(db: Session, user_id: uuid.UUID) -> str:
    counts = dict(db.query(Scan.status, func.count()).filter(Scan.user_id == user_id).group_by(Scan.status).all())
    analysed = counts.get(ScanStatus.analyzed, 0)
    if analysed:
        return f"Analysed ({analysed} scan{'s' if analysed > 1 else ''})"
    if counts.get(ScanStatus.error):
        return "Analysis error, no result yet"
    if counts.get(ScanStatus.quality_failed):
        return "Photo not accepted, no result yet"
    if counts.get(ScanStatus.pending):
        return "Started, not finished"
    return "Not started"


def row_values(db: Session, user: User, now: datetime) -> list:
    consent = (f"Privacy notice accepted {_when(user.consented_at)} (version {user.consent_version})"
               if user.consented_at else "Not recorded")
    consent += (f"; report sending agreed {_when(user.report_consent_at)}" if user.report_consent_at
                else "; report sending not agreed")
    email_status = f"Verified {_when(user.email_verified_at)}" if user.email_verified_at else "Not verified"
    if not user.whatsapp:
        phone_status = "No number"
    else:
        phone_status = f"Verified {_when(user.whatsapp_verified_at)}" if user.whatsapp_verified_at else "Not verified"
    by_column = {"Customer ID": str(user.id), "Date Added": _when(user.created_at), "Customer Name": user.name or "",
                 "Email": user.email, "Phone / WhatsApp Number": user.whatsapp or "", "Consent Status": consent,
                 "Email Verification Status": email_status, "Phone Verification Status": phone_status,
                 "Analysis Status": _analysis_status(db, user.id), "Last Updated": _when(now)}
    return [None if name in TEAM_COLUMNS else by_column[name] for name in COLUMNS]


# ---------- the worksheet ----------


def _padded(row: list) -> list:
    return [("" if c is None else c) for c in row] + [""] * (len(COLUMNS) - len(row))


def _read(http, cells: str) -> list[list]:
    answer = google_sheets.request(http, "GET", google_sheets.values_path(google_sheets.a1(cells)),
                                   params={"majorDimension": "ROWS", "valueRenderOption": "UNFORMATTED_VALUE"})
    return [_padded(r) for r in answer.get("values") or []]


def read_sheet(http) -> list[list]:
    """The worksheet's data rows (row 2 onwards, in sheet order), after checking row 1 is exactly COLUMNS."""
    values = _read(http, f"A:{LAST_COLUMN}")
    if not values or [str(h).strip() for h in values[0]] != list(COLUMNS):
        raise SheetsError("worksheet_columns_mismatch")
    return values[1:]


def _confirm(http, row_number: int, values: list) -> None:
    """Read the row back: it must hold this Customer ID and exactly the app's values."""
    got = (_read(http, f"A{row_number}:{LAST_COLUMN}{row_number}") or [[""] * len(COLUMNS)])[0]
    if str(got[0]).strip() != values[0]:
        raise SheetsError("row_moved", transient=True, other_customer=str(got[0]).strip())
    if any(sent is not None and str(got[i]) != sent for i, sent in enumerate(values)):
        raise SheetsError("write_not_confirmed", transient=True)


def upsert_row(http, values: list) -> str:
    """Write one customer's row: update it where their Customer ID is, else append it. Returns 'updated' or 'added'.
    Only returns once Google shows the written values."""
    customer_id = values[0]
    rows = read_sheet(http)
    found = [i for i, row in enumerate(rows) if str(row[0]).strip() == customer_id]
    if len(found) > 1:
        raise SheetsError("duplicate_customer_rows")  # someone copied a row: the team decides which one stays
    write = {"valueInputOption": "RAW"}
    if found:
        # Customer ID and the team's columns are sent as null (skipped). If a team member sorted the sheet between
        # the lookup and the write, the read-back shows another ID there: that customer is re-queued and repaired.
        n = found[0] + 2  # row 1 is the header
        cells = google_sheets.a1(f"A{n}:{LAST_COLUMN}{n}")
        google_sheets.request(http, "PUT", google_sheets.values_path(cells), params=write,
                              body={"range": cells, "majorDimension": "ROWS", "values": [[None] + values[1:]]})
        _confirm(http, n, values)
        return "updated"
    answer = google_sheets.request(http, "POST", google_sheets.values_path(google_sheets.a1(f"A1:{LAST_COLUMN}1"), ":append"),
                                   params={**write, "insertDataOption": "INSERT_ROWS"},
                                   body={"majorDimension": "ROWS", "values": [["" if v is None else v for v in values]]})
    m = re.search(r"![A-Z]+(\d+)", str(answer.get("updates", {}).get("updatedRange", "")))
    if not m:
        raise SheetsError("write_not_confirmed", transient=True)  # the retry finds the row by Customer ID
    _confirm(http, int(m.group(1)), values)
    return "added"


# ---------- writing queued rows ----------


def _backoff(job: CustomerSheetSync, exc: SheetsError) -> timedelta:
    if not exc.transient:
        return PERMANENT_BACKOFF
    wait = min(timedelta(seconds=60 * 2 ** max(0, job.attempts - 1)), MAX_BACKOFF)
    return max(wait, timedelta(seconds=exc.retry_after or 0))


def _failed(db: Session, job: CustomerSheetSync, exc: SheetsError) -> None:
    now = datetime.utcnow()
    job.attempts += 1
    job.status, job.last_error, job.claimed_at, job.updated_at = "failed", exc.code, None, now
    job.next_attempt_at = now + _backoff(job, exc)
    logger.warning("Customer sheet: row for customer %s not written (%s, attempt %d)", job.user_id, exc.code, job.attempts)
    if exc.other_customer:
        try:
            other = db.get(User, uuid.UUID(exc.other_customer))
        except ValueError:
            other = None
        if other is not None:
            mark_changed(db, other)


def process_due(db: Session, limit: int = 25, http=None) -> dict:
    """Write the rows that are due. Counts only in the result; never raises for Google problems."""
    if not settings.customer_sheet_sync_enabled:
        return {"skipped": "disabled"}
    if google_sheets.config_problems():
        return {"skipped": "not_configured"}
    now = datetime.utcnow()
    jobs = (db.query(CustomerSheetSync)
            .filter(or_(and_(CustomerSheetSync.status.in_(("pending", "failed")), CustomerSheetSync.next_attempt_at <= now),
                        and_(CustomerSheetSync.status == "syncing", CustomerSheetSync.claimed_at < now - STALE_CLAIM)))
            .order_by(CustomerSheetSync.next_attempt_at).limit(limit).with_for_update(skip_locked=True).all())
    for job in jobs:
        job.status, job.claimed_at, job.claimed_version = "syncing", now, job.wanted_version
    db.commit()
    result = {"synced": 0, "failed": 0, "not_eligible": 0}
    if not jobs:
        return result
    with (http or google_sheets.client()) as h:
        for job in jobs:
            user = db.get(User, job.user_id)
            if user is None or not eligible(user):
                job.status, job.claimed_at, job.last_error = "not_eligible", None, None
                result["not_eligible"] += 1
                db.commit()
                continue
            try:
                outcome = upsert_row(h, row_values(db, user, datetime.utcnow()))
            except SheetsError as exc:
                _failed(db, job, exc)
                result["failed"] += 1
            except Exception as exc:  # our own bug: logged by type only (its text could hold customer data)
                _failed(db, job, SheetsError(f"internal_{type(exc).__name__}", transient=True))
                result["failed"] += 1
            else:
                db.refresh(job, attribute_names=["wanted_version"])
                job.synced_version, job.attempts, job.last_error = job.claimed_version, 0, None
                job.last_synced_at = job.updated_at = datetime.utcnow()
                job.claimed_at = None
                job.status = "synced" if job.wanted_version == job.claimed_version else "pending"
                logger.info("Customer sheet: row for customer %s %s", job.user_id, outcome)
                result["synced"] += 1
            db.commit()
    return result


def run_in_background() -> None:
    """After a customer request: write due rows (theirs and earlier failures). Never raises."""
    if not settings.customer_sheet_sync_enabled:
        return
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        process_due(db)
    except Exception as exc:
        logger.error("Customer sheet: background sync stopped (%s)", type(exc).__name__)
    finally:
        db.close()


# ---------- operator tools (scripts/customer_sheet.py) ----------


def status_counts(db: Session) -> dict:
    by_status = dict(db.query(CustomerSheetSync.status, func.count()).group_by(CustomerSheetSync.status).all())
    errors = dict(db.query(CustomerSheetSync.last_error, func.count())
                  .filter(CustomerSheetSync.status == "failed").group_by(CustomerSheetSync.last_error).all())
    return {"by_status": by_status, "failed_by_error": errors}


def retry_failed(db: Session) -> int:
    """Make every failed row due now. Returns how many."""
    n = (db.query(CustomerSheetSync).filter(CustomerSheetSync.status == "failed")
         .update({CustomerSheetSync.next_attempt_at: datetime.utcnow()}, synchronize_session=False))
    db.commit()
    return n


def reconcile(db: Session, apply: bool = False, rewrite_all: bool = False) -> dict:
    """Customers who accepted the spreadsheet notice but have no queued row, and, with rewrite_all, every eligible
    customer (re-adds rows deleted in the sheet, repairs edited app columns). Dry run unless apply."""
    users = (db.query(User).filter(User.consented_at.isnot(None), User.consent_version >= TRACKER_NOTICE_FROM,
                                   User.whatsapp_verified_at.isnot(None)).all())
    queued = {j.user_id for j in db.query(CustomerSheetSync.user_id).all()}
    missing = [u for u in users if u.id not in queued]
    targets = users if rewrite_all else missing
    if apply:
        for user in targets:
            mark_changed(db, user)
        db.commit()
    return {"eligible": len(users), "not_queued": len(missing), "queued_now": len(targets) if apply else 0,
            "would_queue": len(targets)}


def connection_test(http=None) -> list[tuple[str, bool, str]]:
    """Read-only checks: settings, service-account token, access to the spreadsheet, the worksheet's columns."""
    checks = []
    problems = google_sheets.config_problems()
    checks.append(("settings", not problems, "; ".join(problems) or "all required settings present"))
    if problems:
        return checks
    with (http or google_sheets.client()) as h:
        try:
            google_sheets.access_token(h, force_refresh=True)
            checks.append(("service account", True, "Google issued an access token"))
            meta = google_sheets.request(h, "GET", google_sheets.spreadsheet_path(),
                                         params={"fields": "properties.title,sheets.properties.title"})
            title = str(meta.get("properties", {}).get("title", ""))
            tabs = [s.get("properties", {}).get("title") for s in meta.get("sheets", [])]
            checks.append(("spreadsheet", True, f"opened '{title}'"))
            name = settings.google_sheets_worksheet_name.strip()
            checks.append(("worksheet", name in tabs, f"tab '{name}' " + ("found" if name in tabs else "not found")))
            if name in tabs:
                rows = read_sheet(h)
                checks.append(("columns", True, f"the {len(COLUMNS)} expected columns, {len(rows)} data row(s)"))
        except SheetsError as exc:
            checks.append(("google", False, exc.code))
    return checks


def _tabs(http) -> dict[str, int]:
    meta = google_sheets.request(http, "GET", google_sheets.spreadsheet_path(),
                                 params={"fields": "sheets.properties(sheetId,title)"})
    return {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta.get("sheets", [])}


def setup_worksheet(http=None) -> list[str]:
    """Prepares an EMPTY spreadsheet: names its only tab GOOGLE_SHEETS_WORKSHEET_NAME (if that tab doesn't exist)
    and writes the 13 column headers into row 1, then freezes it. Refuses if the tab holds anything else."""
    name = settings.google_sheets_worksheet_name.strip()
    done = []
    with (http or google_sheets.client()) as h:
        tabs = _tabs(h)
        if name not in tabs:
            if len(tabs) != 1:
                raise SheetsError("setup_needs_a_single_tab_or_an_existing_target_tab")
            (old, sheet_id), = tabs.items()
            old_cells = google_sheets.request(h, "GET", google_sheets.values_path("'" + old.replace("'", "''") + "'!A:Z")).get("values")
            if old_cells:
                raise SheetsError("setup_refused_tab_not_empty")
            google_sheets.request(h, "POST", google_sheets.spreadsheet_path(":batchUpdate"), body={"requests": [
                {"updateSheetProperties": {"properties": {"sheetId": sheet_id, "title": name}, "fields": "title"}}]})
            done.append(f"renamed the only tab '{old}' to '{name}'")
            tabs = _tabs(h)
        values = _read(h, f"A:{LAST_COLUMN}")
        if values and [str(c).strip() for c in values[0]] == list(COLUMNS):
            done.append("row 1 already holds the 13 columns")
        elif values:
            raise SheetsError("setup_refused_tab_not_empty")
        else:
            cells = google_sheets.a1(f"A1:{LAST_COLUMN}1")
            google_sheets.request(h, "PUT", google_sheets.values_path(cells), params={"valueInputOption": "RAW"},
                                  body={"range": cells, "majorDimension": "ROWS", "values": [list(COLUMNS)]})
            google_sheets.request(h, "POST", google_sheets.spreadsheet_path(":batchUpdate"), body={"requests": [
                {"updateSheetProperties": {"properties": {"sheetId": tabs[name], "gridProperties": {"frozenRowCount": 1}},
                                           "fields": "gridProperties.frozenRowCount"}}]})
            done.append("wrote the 13 column headers in row 1 and froze it")
        read_sheet(h)  # confirms the header as the sync reads it
    return done


def _delete_test_row(h, test_id: str) -> str:
    """Deletes the one row holding test_id (a TEST- ID only), after re-reading it right before the delete."""
    if not test_id.startswith("TEST-"):
        raise SheetsError("cleanup_refused_not_a_test_row")
    found = [i for i, r in enumerate(read_sheet(h)) if str(r[0]).strip() == test_id]
    if len(found) != 1:
        raise SheetsError("cleanup_refused_row_not_found_once")
    n = found[0] + 2
    if str((_read(h, f"A{n}:A{n}") or [[""]])[0][0]).strip() != test_id:
        raise SheetsError("cleanup_refused_row_moved")
    sheet_id = _tabs(h)[settings.google_sheets_worksheet_name.strip()]
    google_sheets.request(h, "POST", google_sheets.spreadsheet_path(":batchUpdate"), body={"requests": [
        {"deleteDimension": {"range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": n - 1, "endIndex": n}}}]})
    if any(str(r[0]).strip() == test_id for r in read_sheet(h)):
        raise SheetsError("cleanup_not_confirmed")
    return f"deleted test row {n}; no {test_id} row remains"


def dummy_write(http=None, cleanup: bool = False) -> list[str]:
    """Writes ONE clearly fake row (Customer ID TEST-...), then writes it again: the second write must update the
    same row. Touches no database record and no real customer. With cleanup, deletes exactly that row afterwards."""
    test_id = f"TEST-{uuid.uuid4().hex[:12]}"
    now = _when(datetime.utcnow())
    values = [test_id, now, "Dummy Test Customer (delete this row)", "dummy.customer@example.com", "+910000000000",
              "Test row - not a customer", "Not verified", "Not verified", "Not started", None, None, None, now]
    with (http or google_sheets.client()) as h:
        rows_before = len(read_sheet(h))
        first = upsert_row(h, values)
        values[COLUMNS.index("Analysis Status")] = "Test row updated"
        second = upsert_row(h, values)
        count = sum(1 for r in read_sheet(h) if str(r[0]).strip() == test_id)
        lines = [f"first write: {first}", f"second write: {second}", f"rows with {test_id}: {count}"]
        if cleanup:
            lines.append(_delete_test_row(h, test_id))
            lines.append(f"data rows before: {rows_before}, after: {len(read_sheet(h))}")
    return lines
