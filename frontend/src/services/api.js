/* Thin client for the YuriWoori FastAPI backend (see backend app/api/v1). */
import { getAdminToken, getUserToken } from "./session";
import { describeFailure, detailText } from "./apiErrors";

// 127.0.0.1, not "localhost": the backend binds IPv4 only, and "localhost" resolves to ::1 first on Windows.
export const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/v1").replace(/\/$/, "");

export class ApiError extends Error {
  /** reason: "network" | "not-found" | "validation" | "server" | "client" (services/apiErrors.js) */
  constructor(message, status, reason = describeFailure(status).kind) {
    super(message);
    this.status = status;
    this.reason = reason;
  }
}

/**
 * @param {string} path  e.g. "/scans"
 * @param {{method?: string, body?: any, auth?: "user"|"admin"|false, raw?: boolean, keepalive?: boolean, headers?: object}} opts
 *   auth: which session token to send (default: the user token when one exists)
 *   raw:  return the Response (for file downloads) instead of parsed JSON
 *   headers: extra request headers (e.g. X-Report-Token for a report link)
 */
export async function api(path, { method = "GET", body, auth = "user", raw = false, keepalive = false, headers: extra = {} } = {}) {
  const headers = { ...extra };
  if (body) headers["Content-Type"] = "application/json";
  const token = auth === "admin" ? getAdminToken() : auth === "user" ? getUserToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(`${API_URL}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined, keepalive });
  } catch {
    // no response at all: server down, wrong address, or a CORS refusal (the browser can't tell them apart)
    const f = describeFailure(0);
    throw new ApiError(f.message, 0, f.kind);
  }
  if (!res.ok) {
    let detail = null;
    try { detail = detailText((await res.json()).detail); } catch { /* non-JSON error body */ }
    const f = describeFailure(res.status, detail);
    throw new ApiError(f.message, res.status, f.kind);
  }
  return raw ? res : res.json();
}
