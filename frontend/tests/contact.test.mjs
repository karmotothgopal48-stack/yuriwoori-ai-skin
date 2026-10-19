import { test } from "node:test";
import assert from "node:assert/strict";
import { maskEmail, normalizeWhatsapp, validateSignup } from "../src/services/contact.js";

test("WhatsApp numbers are read like the backend does", () => {
  for (const [raw, want] of [["9876543210", "+919876543210"], ["098765 43210", "+919876543210"], ["+91 98765-43210", "+919876543210"],
    ["0091 9876543210", "+919876543210"], ["+1 (415) 555-0123", "+14155550123"], ["+44 7700 900123", "+447700900123"]]) {
    assert.equal(normalizeWhatsapp(raw), want, raw);
  }
  for (const bad of ["", "12345", "+91 98765", "abc9876543210", "5876543210", "+0123456789", "1234567890123456"]) {
    assert.equal(normalizeWhatsapp(bad), null, bad);
  }
});

test("the form needs a name, a WhatsApp number and an email", () => {
  assert.deepEqual(validateSignup({ name: "Priya", whatsapp: "9876543210", email: "priya@example.com" }), { name: "", whatsapp: "", email: "" });
  const errors = validateSignup({ name: " ", whatsapp: "123", email: "nope" });
  assert.ok(errors.name && errors.whatsapp && errors.email);
});

test("a saved customer's email is shown masked, like the backend masks it", () => {
  assert.equal(maskEmail("priya.sharma@example.com"), "p•••@example.com");
  assert.equal(maskEmail(""), "");
  assert.equal(maskEmail(undefined), "");
  assert.equal(maskEmail("no-at-sign"), "");
});
