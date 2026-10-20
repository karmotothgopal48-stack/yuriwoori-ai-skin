import { test } from "node:test";
import assert from "node:assert/strict";
import { YURIWOORI_WHATSAPP_NUMBER, productEnquiryMessage, whatsappProductLink } from "../src/services/whatsapp.js";

// Test fixture: an existing official product, as Routine.jsx receives it (live title + official page).
const foam = {
  name: "Yuri Woori Rice Facial Deep Cleansing Foam",
  url: "https://yuriwoori.com/products/rice-facial-deep-cleansing-foam",
};

const expectedMessage = (p) =>
  `Hi YuriWoori, I'm interested in ${p.name}.\n\nProduct:\n${p.url}\n\nCan you please help me with this product?`;

test("the official number from yuriwoori.com, digits only", () => {
  assert.equal(YURIWOORI_WHATSAPP_NUMBER, "918655954965");
  assert.match(YURIWOORI_WHATSAPP_NUMBER, /^\d+$/);
});

test("the enquiry message names the product and links its official page", () => {
  assert.equal(productEnquiryMessage(foam), expectedMessage(foam));
});

test("the link goes to the official number with the encoded product enquiry", () => {
  const href = whatsappProductLink(foam);
  const link = new URL(href);
  assert.equal(link.protocol, "https:");
  assert.equal(link.hostname, "wa.me");
  assert.equal(link.pathname, `/${YURIWOORI_WHATSAPP_NUMBER}`);
  assert.deepEqual([...link.searchParams.keys()], ["text"]);

  const text = link.searchParams.get("text");
  assert.equal(text, expectedMessage(foam));
  assert.ok(text.includes(foam.name));
  assert.ok(text.includes(foam.url));

  // the product page is only in the message, never the destination
  assert.ok(!link.pathname.includes("yuriwoori.com") && !link.hostname.includes("yuriwoori"));
  // encoded exactly once with encodeURIComponent: no raw spaces or line breaks, no double encoding
  const raw = href.slice(href.indexOf("?text=") + "?text=".length);
  assert.equal(raw, encodeURIComponent(expectedMessage(foam)));
  assert.ok(!/[ \n]/.test(raw));
  assert.ok(!raw.includes("%25"), "not double-encoded");
});

test("names with spaces, apostrophes, ampersands and parentheses stay intact", () => {
  for (const name of ["Aqua Hyaluronic Moisture Cream / Cloud Cream", "Yuri's Glow & Care (50 ml)", "Aloe + Witch Hazel #2 100%"]) {
    const product = { name, url: "https://yuriwoori.com/products/example?variant=1&ref=a" };
    const link = new URL(whatsappProductLink(product));
    assert.equal(link.hostname, "wa.me");
    assert.equal(link.pathname, `/${YURIWOORI_WHATSAPP_NUMBER}`);
    assert.deepEqual([...link.searchParams.keys()], ["text"], "an & in the name or URL must not split the query");
    assert.equal(link.searchParams.get("text"), expectedMessage(product));
  }
});

test("no link without a real product name and URL", () => {
  assert.equal(whatsappProductLink({ name: "X", url: null }), null);
  assert.equal(whatsappProductLink({ name: "", url: foam.url }), null);
  assert.equal(whatsappProductLink({ name: foam.name }), null);
  assert.equal(whatsappProductLink(null), null);
});
