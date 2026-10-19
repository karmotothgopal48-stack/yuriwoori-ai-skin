/* Pure presentation logic for the report and its delivery (no imports, so it is unit-tested with node --test).
   Wording follows what the backend recorded: a message is "sent" only when the provider confirmed it. */

export const CHANNEL_LABELS = { email: "Email", whatsapp: "WhatsApp" };

/** "#t=<token>" -> the token, or null. The token stays in the URL fragment, which browsers never send to servers. */
export function parseReportToken(hash) {
  const m = /^#t=([A-Za-z0-9_-]{20,100})$/.exec(hash ?? "");
  return m ? m[1] : null;
}

const time = (iso) => {
  if (!iso) return "";
  const d = new Date(/Z|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`); // the API sends UTC without a zone
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
};

/**
 * One channel's delivery (backend DeliveryInfo) -> { kind, text, action }.
 * action: "consent" (ask to send), "code" (confirm the contact first), "retry", "check" (look again later) or null.
 */
export function deliveryView(d) {
  const to = d.destination ? ` to ${d.destination}` : "";
  const label = CHANNEL_LABELS[d.channel] ?? d.channel;
  switch (d.status) {
    case "delivered":
      return { kind: "delivered", text: `Delivered${to}${d.sent_at ? ` (sent ${time(d.sent_at)})` : ""}.`, action: null };
    case "sent":
      return { kind: "sent", text: d.channel === "email"
        ? `Sent${to}${d.sent_at ? ` on ${time(d.sent_at)}` : ""}. It can take a few minutes to arrive — please also check your spam folder.`
        : `Sent by WhatsApp${to}${d.sent_at ? ` on ${time(d.sent_at)}` : ""}.`, action: null };
    case "accepted":
      return { kind: "pending", text: `WhatsApp accepted your report${to} and is sending it. This page updates when WhatsApp confirms.`, action: "check" };
    case "sending":
      return { kind: "pending", text: `Sending your report${to}…`, action: "check" };
    case "failed":
      return { kind: "failed", text: `Your report couldn't be sent${to}.${d.can_retry ? " You can try again." : ""}`, action: d.can_retry ? "retry" : null };
    default: // pending: say exactly what it is waiting for
      if (d.reason === "not_configured") return { kind: "unavailable", text: `Sending by ${label} isn't set up yet, so nothing has been sent.`, action: "check" };
      if (d.reason === "contact_changed") return { kind: "unavailable", text: `This report was made for the ${label} contact you had then, which has since changed, so it isn't sent to the new one. Run a new analysis to receive a report there.`, action: null };
      if (d.reason === "no_contact") return { kind: "unavailable", text: `There's no ${label} contact saved for you.`, action: null };
      if (d.reason === "test_mode") return { kind: "unavailable", text: `Sending by ${label} is limited to test contacts at the moment, so nothing has been sent${to}.`, action: null };
      if (d.reason === "no_consent") return { kind: "ask", text: `Would you like your report sent${to}?`, action: "consent" };
      if (d.reason === "mobile_verification_unavailable") return { kind: "unavailable", text: "Your report is sent once your mobile number is verified, and mobile verification isn't available at the moment, so nothing has been sent. You can download the PDF meanwhile.", action: "check" };
      if (d.reason === "mobile_not_verified") return d.channel === "whatsapp"
        ? { kind: "ask", text: `Verify your mobile number${to} with a 6-digit code, and we'll send your report.`, action: "code" }
        : { kind: "ask", text: "Verify your mobile number to receive your report.", action: null };
      if (d.reason === "not_verified") return { kind: "ask", text: `Confirm${to} is yours with a 6-digit code, and we'll send your report.`, action: "code" };
      return { kind: "pending", text: `Your report is waiting to be sent${to}.`, action: d.can_retry ? "retry" : "check" };
  }
}

/** Contacts to verify right after signup (GET /delivery/status): the mobile (WhatsApp) number, whenever it can
    receive a code and isn't verified yet. Mobile verification is required before any report is sent, by any
    channel; the email address needs no code (unless the server's policy asks for one, on the results page). */
export const contactsToConfirm = (status) =>
  (status?.whatsapp?.available && !status.whatsapp.verified ? ["whatsapp"] : []);

/** Keep looking for updates while a message is on its way. */
export const shouldPoll = (deliveries) => (deliveries ?? []).some((d) => d.status === "sending" || d.status === "accepted");

export const money = (n) => (n == null ? "" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`);
