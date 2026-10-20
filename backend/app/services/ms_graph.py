"""LEGACY, NOT USED: replaced by app/services/google_sheets.py (Google Sheets). Nothing imports this module; it is
kept only for rollback (README "Customer follow-up spreadsheet" > Rollback) and can be deleted once approved.

Microsoft Graph access for the customer follow-up workbook.

Microsoft documents the Excel workbook API (table rows, ranges) as delegated-only: "Application: Not supported",
least privilege Files.ReadWrite, and only for workbooks on the business platform (OneDrive for Business,
SharePoint), not personal OneDrive. So the backend acts as one Microsoft 365 work/school account:
  - signed in once by an admin with the OAuth 2.0 device code flow (scripts/customer_sheet.py login),
  - then kept signed in with refresh tokens (Microsoft identity platform v2.0 token endpoint).
The tokens live only in a backend file (MS_GRAPH_TOKEN_CACHE_PATH, git- and docker-ignored); they are never
logged, returned by the API or sent to the browser. Errors carry only a short code (Graph's error code or an HTTP
status), never Graph's message text or anything from the workbook.

MSAL Python is the usual library for this; it isn't installed in this project, so the two documented endpoints
(devicecode, token) are called directly with httpx. Swapping in msal later changes only this file."""

import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"
LOGIN = "https://login.microsoftonline.com"
BACKEND_DIR = Path(__file__).resolve().parents[2]
# Tenants that mean "any account": personal Microsoft accounts can't use the Excel API, so a real tenant is required.
NOT_A_TENANT = {"common", "consumers", "organizations", "9188040d-6c67-4c5b-b112-36a304b66dad"}
GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
DOMAIN = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,254}$")
TRANSIENT_STATUS = {409, 423, 429, 500, 502, 503, 504}

_lock = threading.Lock()


class GraphError(Exception):
    """code: a short, safe label (no personal data, no secrets). transient: worth retrying soon."""

    def __init__(self, code: str, *, status: int | None = None, retry_after: float | None = None,
                 transient: bool = False, other_customer: str | None = None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.retry_after = retry_after
        self.transient = transient
        self.other_customer = other_customer  # set by customer_sheet when a sorted table moved the target row


def _safe_code(value) -> str:
    return re.sub(r"[^A-Za-z0-9_.]", "", str(value or ""))[:60] or "unknown"


def config_problems() -> list[str]:
    """What is missing or invalid in the Graph/workbook settings (setting names only, never their values)."""
    problems = []
    tenant = settings.ms_graph_tenant_id.strip()
    if not tenant:
        problems.append("MS_GRAPH_TENANT_ID is missing")
    elif tenant.lower() in NOT_A_TENANT:
        problems.append("MS_GRAPH_TENANT_ID must be your Microsoft 365 organisation's tenant ID (the Excel API "
                        "doesn't support personal Microsoft accounts or the 'common' endpoints)")
    elif not (GUID.match(tenant) or DOMAIN.match(tenant)):
        problems.append("MS_GRAPH_TENANT_ID is not a tenant ID (GUID) or tenant domain")
    client_id = settings.ms_graph_client_id.strip()
    if not client_id:
        problems.append("MS_GRAPH_CLIENT_ID is missing")
    elif not GUID.match(client_id):
        problems.append("MS_GRAPH_CLIENT_ID is not an application (client) ID (GUID)")
    if not settings.ms_graph_scopes.split():
        problems.append("MS_GRAPH_SCOPES is empty")
    if not settings.customer_sheet_drive_id.strip():
        problems.append("CUSTOMER_SHEET_DRIVE_ID is missing")
    if not settings.customer_sheet_item_id.strip():
        problems.append("CUSTOMER_SHEET_ITEM_ID is missing")
    if not TABLE_NAME.match(settings.customer_sheet_table.strip()):
        problems.append("CUSTOMER_SHEET_TABLE is not a valid Excel table name")
    return problems


def scopes() -> str:
    return " ".join(sorted(set(settings.ms_graph_scopes.split()) | {"offline_access"}))


def client() -> httpx.Client:
    return httpx.Client(timeout=settings.ms_graph_timeout_seconds)


# ---------- the backend's token cache (a file only the backend reads) ----------


def cache_path() -> Path:
    path = Path(settings.ms_graph_token_cache_path)
    return path if path.is_absolute() else BACKEND_DIR / path


def _load() -> dict | None:
    try:
        return json.loads(cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(data: dict) -> None:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)  # owner only (best effort; Windows keeps the folder's ACL)
    except OSError:
        pass
    os.replace(tmp, path)


def _remember(answer: dict, previous: dict | None = None) -> str:
    refresh = answer.get("refresh_token") or (previous or {}).get("refresh_token")
    if not answer.get("access_token") or not refresh:
        raise GraphError("auth_incomplete_answer")
    _save({"tenant_id": settings.ms_graph_tenant_id.strip(), "client_id": settings.ms_graph_client_id.strip(),
           "access_token": answer["access_token"], "refresh_token": refresh,
           "expires_at": time.time() + int(answer.get("expires_in") or 3600), "scope": answer.get("scope", ""),
           "signed_in_at": (previous or {}).get("signed_in_at") or datetime.utcnow().isoformat(timespec="seconds")})
    return answer["access_token"]


def sign_in_state() -> str:
    """'signed_in', 'not_signed_in', or 'other_app' (the cache belongs to another tenant/client ID)."""
    data = _load()
    if not data or not data.get("refresh_token"):
        return "not_signed_in"
    if data.get("tenant_id") != settings.ms_graph_tenant_id.strip() or data.get("client_id") != settings.ms_graph_client_id.strip():
        return "other_app"
    return "signed_in"


def _token_endpoint(http: httpx.Client, form: dict) -> httpx.Response:
    try:
        return http.post(f"{LOGIN}/{settings.ms_graph_tenant_id.strip()}/oauth2/v2.0/token", data=form)
    except httpx.TimeoutException:
        raise GraphError("auth_timeout", transient=True)
    except httpx.HTTPError:
        raise GraphError("auth_network", transient=True)


def _auth_error(r: httpx.Response) -> GraphError:
    try:
        error = r.json().get("error")
    except ValueError:
        error = None
    if error == "invalid_grant":  # refresh token expired/revoked, password changed, consent removed: sign in again
        return GraphError("auth_expired_sign_in_again", status=r.status_code)
    transient = r.status_code >= 500 or error == "temporarily_unavailable"
    return GraphError(f"auth_{_safe_code(error or r.status_code)}", status=r.status_code, transient=transient)


def access_token(http: httpx.Client, force_refresh: bool = False) -> str:
    with _lock:
        state = sign_in_state()
        if state != "signed_in":
            raise GraphError(state)
        data = _load()
        if not force_refresh and data.get("access_token") and data.get("expires_at", 0) > time.time() + 120:
            return data["access_token"]
        r = _token_endpoint(http, {"grant_type": "refresh_token", "client_id": settings.ms_graph_client_id.strip(),
                                   "refresh_token": data["refresh_token"], "scope": scopes()})
        if r.status_code != 200:
            raise _auth_error(r)
        return _remember(r.json(), data)


def device_code_login(show, http: httpx.Client | None = None, sleep=time.sleep) -> None:
    """Interactive admin sign-in: shows Microsoft's instruction (a URL and a one-time code to type there), then
    waits until the admin has signed in with the work/school account the backend will act as."""
    problems = [p for p in config_problems() if p.startswith(("MS_GRAPH_TENANT_ID", "MS_GRAPH_CLIENT_ID", "MS_GRAPH_SCOPES"))]
    if problems:
        raise GraphError("not_configured: " + "; ".join(problems))
    with (http or client()) as h:
        try:
            r = h.post(f"{LOGIN}/{settings.ms_graph_tenant_id.strip()}/oauth2/v2.0/devicecode",
                       data={"client_id": settings.ms_graph_client_id.strip(), "scope": scopes()})
        except httpx.HTTPError:
            raise GraphError("auth_network", transient=True)
        if r.status_code != 200:
            raise _auth_error(r)
        start = r.json()
        show(start["message"])
        interval, deadline = int(start.get("interval") or 5), time.time() + int(start.get("expires_in") or 900)
        while time.time() < deadline:
            sleep(interval)
            r = _token_endpoint(h, {"grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                                    "client_id": settings.ms_graph_client_id.strip(), "device_code": start["device_code"]})
            if r.status_code == 200:
                with _lock:
                    _remember(r.json())
                return
            error = (r.json() if r.content else {}).get("error")
            if error == "authorization_pending":
                continue
            if error == "slow_down":
                interval += 5
                continue
            raise _auth_error(r)
        raise GraphError("auth_device_code_expired")


# ---------- Graph requests ----------


def _retry_after(r: httpx.Response) -> float | None:
    value = r.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, (parsedate_to_datetime(value) - datetime.now(parsedate_to_datetime(value).tzinfo)).total_seconds())
        except (TypeError, ValueError):
            return None


def request(http: httpx.Client, method: str, path: str, body: dict | None = None) -> dict:
    """One Graph call as the signed-in account. A 401 refreshes the token once; everything else maps to GraphError."""
    token = access_token(http)
    for attempt in (1, 2):
        try:
            r = http.request(method, GRAPH + path, json=body, headers={"Authorization": f"Bearer {token}"})
        except httpx.TimeoutException:  # the write may still have happened: callers look the row up before retrying
            raise GraphError("timeout", transient=True)
        except httpx.HTTPError:
            raise GraphError("network", transient=True)
        if r.status_code == 401 and attempt == 1:
            token = access_token(http, force_refresh=True)
            continue
        break
    if r.is_success:
        return r.json() if r.content else {}
    try:
        code = _safe_code(r.json().get("error", {}).get("code"))
    except (ValueError, AttributeError):
        code = "unknown"
    label = {401: "unauthorized", 403: "forbidden", 404: "not_found"}.get(r.status_code, f"http_{r.status_code}")
    raise GraphError(f"{label}_{code}", status=r.status_code, retry_after=_retry_after(r),
                     transient=r.status_code in TRANSIENT_STATUS)
