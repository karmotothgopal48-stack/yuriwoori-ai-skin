"""Google Sheets API (v4) access for the customer follow-up sheet (app/services/customer_sheet.py).

Authentication: a Google Cloud service account, server to server (OAuth 2.0 JWT bearer grant, the flow Google
documents for "Server to Server Applications"). The spreadsheet owner shares the sheet with the service account's
email (Editor); the account sees nothing else. Scope: https://www.googleapis.com/auth/spreadsheets.
  - The service account's JSON key is created by the owner in Google Cloud Console and stored OUTSIDE this project
    (GOOGLE_SERVICE_ACCOUNT_FILE); a key inside the project folder is refused (it could be committed or copied).
  - The signed request is made with Google's official google-auth library (google.auth.crypt / google.auth.jwt,
    imported only when needed); the token exchange is the documented HTTPS call to oauth2.googleapis.com.
  - Access tokens are kept in memory only. Nothing here logs or returns the key, a token, or Google's error text;
    errors carry a short code (HTTP status + Google's status/reason)."""

import json
import logging
import re
import threading
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SHEETS = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPE = "https://www.googleapis.com/auth/spreadsheets"
TOKEN_URI = "https://oauth2.googleapis.com/token"  # always this one, whatever a key file says
PROJECT_DIR = Path(__file__).resolve().parents[3]
SPREADSHEET_ID = re.compile(r"^[A-Za-z0-9_-]{20,200}$")
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
QUOTA_REASONS = {"RATE_LIMIT_EXCEEDED", "RESOURCE_EXHAUSTED", "rateLimitExceeded", "userRateLimitExceeded"}

_lock = threading.Lock()
_token: dict = {}


class SheetsError(Exception):
    """code: a short, safe label (no personal data, no secrets). transient: worth retrying soon."""

    def __init__(self, code: str, *, status: int | None = None, retry_after: float | None = None,
                 transient: bool = False, other_customer: str | None = None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.retry_after = retry_after
        self.transient = transient
        self.other_customer = other_customer  # set by customer_sheet when a sorted sheet moved the target row


def _safe(value) -> str:
    return re.sub(r"[^A-Za-z0-9_.]", "", str(value or ""))[:60] or "unknown"


def google_auth_available() -> bool:
    try:
        import google.auth.crypt  # noqa: F401
        import google.auth.jwt  # noqa: F401
        return True
    except ImportError:
        return False


def key_file() -> Path | None:
    raw = settings.google_service_account_file.strip()
    return Path(raw).expanduser().resolve() if raw else None


def _key_info() -> dict:
    path = key_file()
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, AttributeError):
        raise SheetsError("credentials_unreadable")
    if not isinstance(info, dict) or info.get("type") != "service_account" or not info.get("client_email") or not info.get("private_key"):
        raise SheetsError("credentials_not_a_service_account_key")
    return info


def service_account_email() -> str | None:
    """The address to share the sheet with (not a secret). None when the key file can't be read."""
    try:
        return str(_key_info()["client_email"])
    except SheetsError:
        return None


def config_problems() -> list[str]:
    """What is missing or invalid (setting names and plain reasons only, never values or key contents)."""
    problems = []
    if not SPREADSHEET_ID.match(settings.google_sheets_spreadsheet_id.strip()):
        problems.append("GOOGLE_SHEETS_SPREADSHEET_ID is missing or not a spreadsheet ID"
                        if settings.google_sheets_spreadsheet_id.strip() else "GOOGLE_SHEETS_SPREADSHEET_ID is missing")
    name = settings.google_sheets_worksheet_name.strip()
    if not name or len(name) > 100 or re.search(r"[\[\]:*?/\\]", name):
        problems.append("GOOGLE_SHEETS_WORKSHEET_NAME is missing or not a valid tab name")
    path = key_file()
    if path is None:
        problems.append("GOOGLE_SERVICE_ACCOUNT_FILE is missing")
    elif PROJECT_DIR == path or PROJECT_DIR in path.parents:
        problems.append("GOOGLE_SERVICE_ACCOUNT_FILE is inside the project folder: move the key outside it")
    elif not path.is_file():
        problems.append("GOOGLE_SERVICE_ACCOUNT_FILE does not point to a file")
    else:
        try:
            _key_info()
        except SheetsError as exc:
            problems.append(f"GOOGLE_SERVICE_ACCOUNT_FILE: {exc.code}")
    if not google_auth_available():
        problems.append("the google-auth package is not installed (needs approval: pip install google-auth)")
    return problems


def config_warnings() -> list[str]:
    path = key_file()
    if path and "onedrive" in str(path).lower():
        return ["GOOGLE_SERVICE_ACCOUNT_FILE is in a OneDrive folder, so the key is uploaded to OneDrive: prefer a "
                "folder that isn't synced, e.g. C:\\Users\\<you>\\.yuriwoori\\"]
    return []


def client() -> httpx.Client:
    return httpx.Client(timeout=settings.google_sheets_timeout_seconds)


# ---------- access token (memory only) ----------


def _signed_assertion(info: dict) -> str:
    """The service account's signed JWT (google-auth signs it with the key; the key never leaves this process)."""
    from google.auth import crypt, jwt as google_jwt
    signer = crypt.RSASigner.from_service_account_info(info)
    now = int(time.time())
    claims = {"iss": info["client_email"], "scope": SCOPE, "aud": TOKEN_URI, "iat": now, "exp": now + 3600}
    token = google_jwt.encode(signer, claims)
    return token.decode() if isinstance(token, bytes) else token


def reset_token() -> None:
    with _lock:
        _token.clear()


def access_token(http: httpx.Client, force_refresh: bool = False) -> str:
    with _lock:
        if not force_refresh and _token.get("value") and _token.get("expires_at", 0) > time.time() + 120:
            return _token["value"]
        info = _key_info()
        try:
            assertion = _signed_assertion(info)
        except ImportError:
            raise SheetsError("google_auth_not_installed")
        except Exception:  # a malformed key: its text is never logged
            raise SheetsError("credentials_invalid_key")
        try:
            r = http.post(TOKEN_URI, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion})
        except httpx.TimeoutException:
            raise SheetsError("auth_timeout", transient=True)
        except httpx.HTTPError:
            raise SheetsError("auth_network", transient=True)
        if r.status_code != 200:
            try:
                error = r.json().get("error")
            except ValueError:
                error = None
            # invalid_grant: key deleted/disabled, service account removed, or this PC's clock is wrong
            raise SheetsError(f"auth_{_safe(error or r.status_code)}", status=r.status_code,
                              transient=r.status_code >= 500)
        answer = r.json()
        if not answer.get("access_token"):
            raise SheetsError("auth_incomplete_answer")
        _token.update(value=answer["access_token"], expires_at=time.time() + int(answer.get("expires_in") or 3600))
        return _token["value"]


# ---------- Sheets requests ----------


def a1(cells: str) -> str:
    """'<worksheet>'!<cells>, with the tab name quoted as Sheets requires."""
    return "'" + settings.google_sheets_worksheet_name.strip().replace("'", "''") + "'!" + cells


def spreadsheet_path(suffix: str = "") -> str:
    return f"{SHEETS}/{quote(settings.google_sheets_spreadsheet_id.strip(), safe='')}{suffix}"


def values_path(range_a1: str, action: str = "") -> str:
    return spreadsheet_path(f"/values/{quote(range_a1, safe='')}{action}")


def _error(r: httpx.Response) -> SheetsError:
    try:
        err = r.json().get("error", {})
    except ValueError:
        err = {}
    status = _safe(err.get("status") or r.status_code)
    reasons = {d.get("reason") for d in err.get("details", []) if isinstance(d, dict)} | \
              {e.get("reason") for e in err.get("errors", []) if isinstance(e, dict)}
    retry_after = None
    try:
        retry_after = float(r.headers["Retry-After"]) if "Retry-After" in r.headers else None
    except ValueError:
        pass
    if "SERVICE_DISABLED" in reasons or "accessNotConfigured" in reasons:
        return SheetsError("sheets_api_not_enabled", status=r.status_code)
    if r.status_code == 400 and "Unable to parse range" in str(err.get("message", "")):
        return SheetsError("worksheet_not_found", status=r.status_code)
    if r.status_code == 429 or reasons & QUOTA_REASONS:
        return SheetsError(f"quota_{status}", status=r.status_code, retry_after=retry_after, transient=True)
    label = {401: "unauthorized", 403: "forbidden", 404: "not_found"}.get(r.status_code, f"http_{r.status_code}")
    return SheetsError(f"{label}_{status}", status=r.status_code, retry_after=retry_after,
                       transient=r.status_code in TRANSIENT_STATUS)


def request(http: httpx.Client, method: str, url: str, params: dict | None = None, body: dict | None = None) -> dict:
    """One Sheets call as the service account. A 401 gets a fresh token once; everything else maps to SheetsError."""
    token = access_token(http)
    for attempt in (1, 2):
        try:
            r = http.request(method, url, params=params, json=body, headers={"Authorization": f"Bearer {token}"})
        except httpx.TimeoutException:  # the write may still have happened: callers look the row up before retrying
            raise SheetsError("timeout", transient=True)
        except httpx.HTTPError:
            raise SheetsError("network", transient=True)
        if r.status_code == 401 and attempt == 1:
            token = access_token(http, force_refresh=True)
            continue
        break
    if r.is_success:
        return r.json() if r.content else {}
    raise _error(r)
