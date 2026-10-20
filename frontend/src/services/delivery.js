/* The customer's skin-analysis report and its delivery (backend /v1/reports and /v1/delivery).
   Reports are only sent to the customer's own email / WhatsApp number, with their consent, after they
   confirm the contact with a one-time code. Delivery states come from the backend (services/reportView.js). */
import { api } from "./api";

export { CHANNEL_LABELS } from "./reportView";

/** Generate the scan's report from its saved analysis (once) and send it wherever it is ready; returns its status. */
export const createReport = (scanId) => api("/reports", { method: "POST", body: { scan_id: scanId } });
export const reportStatus = (scanId) => api(`/reports/scan/${scanId}`);
/** Per channel: { available, verified, destination (masked) }, plus report_consent. */
export const deliveryStatus = () => api("/delivery/status");
export const sendCode = (channel) => api("/delivery/verify/start", { method: "POST", body: { channel } });
export const confirmCode = (channel, code) => api("/delivery/verify/confirm", { method: "POST", body: { channel, code } });
/** Send or safely retry on one channel (asking for it is the consent to have it sent). */
export const sendReport = (scanId, channel) => api(`/delivery/scans/${scanId}/send`, { method: "POST", body: { channel } });

/** The report behind a secret link (the token goes in a header, never in the request URL). */
export const sharedReport = (token) => api("/reports/shared", { auth: false, headers: { "X-Report-Token": token } });

async function saveFile(res, filename) {
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const downloadOwnReportPdf = async (scanId) =>
  saveFile(await api(`/reports/scan/${scanId}/pdf`, { raw: true }), "YuriWoori-skin-report.pdf");
export const downloadSharedReportPdf = async (token) =>
  saveFile(await api("/reports/shared/pdf", { raw: true, auth: false, headers: { "X-Report-Token": token } }), "YuriWoori-skin-report.pdf");

/** A Shopify cart with these variants (one each), priced by Shopify now; returns { checkout_url, subtotal, discounts, total }. */
export const shopifyCart = (variantIds) =>
  api("/shopify/cart", { method: "POST", auth: false, body: { lines: variantIds.map((v) => ({ variant_id: v, quantity: 1 })) } });
