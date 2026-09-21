/* Thin client for the YuriWoori FastAPI backend (see backend app/api/v1). */
export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000/v1").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// FastAPI returns `detail` as a string, or as a list of validation errors (422).
const detailText = (detail) =>
  typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : null;

export async function api(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the YuriWoori server. Check that the backend is running and try again.", 0);
  }
  if (!res.ok) {
    let detail = null;
    try { detail = detailText((await res.json()).detail); } catch { /* non-JSON error body */ }
    throw new ApiError(detail || `Request failed (${res.status}).`, res.status);
  }
  return res.json();
}
