import { test } from "node:test";
import assert from "node:assert/strict";
import { deliveryView, parseReportToken, shouldPoll } from "../src/services/reportView.js";

const base = { channel: "email", destination: "p•••@example.com", status: "pending", reason: null, can_retry: false, sent_at: null, attempts: 0 };

test("report links carry the token only in the fragment", () => {
  const token = "AbC_def-123456789012345678901234567890abcd";
  assert.equal(parseReportToken(`#t=${token}`), token);
  for (const bad of ["", "#", "#t=", "#t=short", `?t=${token}`, `#t=${token}&x=1`, "#t=<script>alert(1)</script>"]) assert.equal(parseReportToken(bad), null, bad);
});

test("nothing is called sent unless the provider confirmed it", () => {
  const sent = deliveryView({ ...base, status: "sent", sent_at: "2026-10-13T11:20:00" });
  assert.equal(sent.kind, "sent"); assert.match(sent.text, /^Sent to p•••@example\.com on /);
  const accepted = deliveryView({ ...base, channel: "whatsapp", destination: "+91•••••••210", status: "accepted" });
  assert.equal(accepted.kind, "pending"); assert.doesNotMatch(accepted.text, /\bsent\b|delivered/i);
  assert.doesNotMatch(deliveryView({ ...base, status: "sending" }).text, /^Sent/);
  assert.equal(deliveryView({ ...base, channel: "whatsapp", status: "delivered" }).kind, "delivered");
});

test("pending says what it waits for and offers the right next step", () => {
  const notConfigured = deliveryView({ ...base, reason: "not_configured" });
  assert.equal(notConfigured.kind, "unavailable"); assert.match(notConfigured.text, /nothing has been sent/); assert.equal(notConfigured.action, "check");
  assert.equal(deliveryView({ ...base, reason: "no_consent" }).action, "consent");
  assert.equal(deliveryView({ ...base, reason: "not_verified" }).action, "code");
  const noMobile = deliveryView({ ...base, channel: "email", reason: "mobile_verification_unavailable" });
  assert.equal(noMobile.kind, "unavailable"); assert.match(noMobile.text, /nothing has been sent/);
  const changed = deliveryView({ ...base, channel: "whatsapp", reason: "contact_changed" });
  assert.equal(changed.action, null); assert.match(changed.text, /has since changed/);
  assert.equal(deliveryView({ ...base, channel: "whatsapp", reason: "mobile_not_verified" }).action, "code");
  const waiting = deliveryView({ ...base, channel: "email", reason: "mobile_not_verified" });
  assert.equal(waiting.action, null); assert.match(waiting.text, /Verify your mobile number to receive your report/);
  assert.equal(deliveryView({ ...base, status: "failed", can_retry: true }).action, "retry");
  assert.equal(deliveryView({ ...base, status: "failed", can_retry: false, reason: "not_configured" }).action, null);
});

test("the page keeps checking only while a message is on its way", () => {
  assert.equal(shouldPoll([{ status: "sent" }, { status: "accepted" }]), true);
  assert.equal(shouldPoll([{ status: "sending" }]), true);
  assert.equal(shouldPoll([{ status: "sent" }, { status: "failed" }, { status: "pending" }]), false);
  assert.equal(shouldPoll(undefined), false);
});

test("after signup only the mobile number is verified, whenever it can receive a code", async () => {
  const { contactsToConfirm } = await import("../src/services/reportView.js");
  const ch = (available, verified) => ({ available, verified, destination: "x" });
  assert.deepEqual(contactsToConfirm({ report_consent: true, email: ch(true, false), whatsapp: ch(true, false) }), ["whatsapp"]); // no email code
  assert.deepEqual(contactsToConfirm({ report_consent: false, email: ch(true, false), whatsapp: ch(true, false) }), ["whatsapp"]); // always asked
  assert.deepEqual(contactsToConfirm({ report_consent: true, email: ch(true, false), whatsapp: ch(true, true) }), []); // already verified
  assert.deepEqual(contactsToConfirm({ report_consent: true, email: ch(true, false), whatsapp: ch(false, false) }), []); // not set up
  assert.deepEqual(contactsToConfirm(null), []);
});
