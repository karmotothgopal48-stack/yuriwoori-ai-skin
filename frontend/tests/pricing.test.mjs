import { test } from "node:test";
import assert from "node:assert/strict";
import { FINAL_PRICE_UNAVAILABLE, currentQuote, discountLabel, discountNote, estimateBeforeDiscounts, priceState, routineLines, slabHint } from "../src/services/pricing.js";

const money = (n) => `₹${Number(n).toLocaleString("en-IN")}`;

test("the store's slab discounts are labelled automatic, never as a code to enter", () => {
  assert.equal(discountLabel({ title: "YWPL1000", kind: "automatic", amount: 1000 }), "Automatic discount YWPL1000");
  assert.equal(discountLabel({ title: "SAVE10", kind: "code", amount: 100 }), "Coupon code SAVE10");
  assert.match(discountNote([{ title: "YWPL1000", kind: "automatic" }]), /no coupon code needed/);
  assert.match(discountNote([]), /No store discount/);
});

test("the slab sentence appears only for a slab summary Shopify verified", () => {
  const slabs = { verified: true, current: { min_subtotal: 3500, amount: 1000, title: "YWPL1000" },
                  next: { min_subtotal: 5500, amount: 1500, title: "YWPL1500" }, add_for_next: 505 };
  assert.equal(slabHint(slabs, money),
    "This order is in the ₹3,500+ slab (₹1,000 off). Add ₹505 more to reach ₹5,500 and get ₹1,500 off instead (YWPL1500, automatic).");
  assert.equal(slabHint({ verified: false }, money), null);
  assert.equal(slabHint(null, money), null);
});

test("the reported 4-product routine: lines for Shopify and the labelled estimate before discounts", () => {
  const byHandle = {
    foam: { variant_id: 1, price: 855, available: true }, toner: { variant_id: 2, price: 765, available: true },
    patch: { variant_id: 3, price: 1350, available: true }, cream: { variant_id: 4, price: 2025, available: true },
    gone: { variant_id: 5, price: 99, available: false },
  };
  const lines = routineLines(["foam", "toner", "patch", "cream", "foam", "gone", "unknown"], byHandle);
  assert.deepEqual(lines, [1, 2, 3, 4].map((v) => ({ variant_id: v, quantity: 1 })));  // duplicates merged, unsellable left out
  assert.equal(estimateBeforeDiscounts(lines, byHandle), 4995);  // only an estimate: Shopify's total is 3995 after YWPL1000
});


test("a total is shown only from Shopify; an estimate only from prices confirmed live; otherwise none", () => {
  const shopify = { subtotal: 4995, discounts: [{ title: "YWPL1000", kind: "automatic", amount: 1000 }], total: 3995 };
  assert.equal(priceState({ shopify, quoteStatus: "ready", pricesConfirmed: false }), "shopify");  // Shopify priced the variants itself
  assert.equal(priceState({ shopify: null, quoteStatus: "loading", pricesConfirmed: true }), "calculating");
  assert.equal(priceState({ shopify: null, quoteStatus: "error", pricesConfirmed: true }), "estimate");
  assert.equal(priceState({ shopify: null, quoteStatus: "error", pricesConfirmed: false }), "unavailable");  // stale/saved prices: no amount
});

test("a slower Shopify answer for an earlier cart never replaces the newer cart's pricing", () => {
  const older = { key: "1:1,2:1", status: "ready", data: { subtotal: 1620, total: 1620 } };
  const newer = { key: "1:1,2:1,3:1,4:1", status: "ready", data: { subtotal: 4995, total: 3995 } };
  assert.equal(currentQuote(older, "1:1,2:1,3:1,4:1"), null);  // arrived late, for lines that are gone: ignored
  assert.deepEqual(currentQuote(newer, "1:1,2:1,3:1,4:1"), newer.data);
  assert.equal(currentQuote({ key: "1:1", status: "error", data: null }, "1:1"), null);
  assert.equal(currentQuote(newer, ""), null);
});

test("while Shopify's pricing is loading or unavailable the wording is exactly the required one", () => {
  assert.equal(FINAL_PRICE_UNAVAILABLE, "Final price unavailable\u2014verify at Shopify checkout.");
});
