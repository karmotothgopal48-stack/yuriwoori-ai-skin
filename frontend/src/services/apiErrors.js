/* What a failed API request means for the user (no React or Vite, so it can be unit-tested with node --test).
   A request that never got a response (server down, wrong address, or a CORS refusal - the browser reports
   all three the same way) is "network"; every response with an error status keeps its own meaning, so a
   404, 422 or 500 is never reported as "the server is not running". */

export const NETWORK_MESSAGE = "Unable to connect to the YuriWoori server. Please make sure the server is running and try again.";

// FastAPI returns `detail` as a string, or as a list of validation errors (422).
export const detailText = (detail) =>
  typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : null;

/** A saved session is only invalid when the server says so (401/403). No response (status 0) or a server error
    says nothing about the session: keep it and try again, rather than signing the customer out. */
export const sessionRejected = (status) => status === 401 || status === 403;

/** { kind, message } for a failed request; status 0 = no response at all. */
export function describeFailure(status, detail = null) {
  if (!status) return { kind: "network", message: NETWORK_MESSAGE };
  if (status === 404) {
    return { kind: "not-found", message: "This request isn't available on the YuriWoori server (404). The server may be running an older version." };
  }
  if (status === 422) return { kind: "validation", message: detail || "Some of the details sent were not accepted. Please check them and try again." };
  if (status === 429) return { kind: "rate-limit", message: "The YuriWoori server is busy right now. Please wait a moment and try again." };
  if (status >= 500) return { kind: "server", message: detail || `The YuriWoori server ran into a problem (${status}). Please try again.` };
  return { kind: "client", message: detail || `Request failed (${status}).` };
}
