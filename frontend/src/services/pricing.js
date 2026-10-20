/* Wording for prices and discounts calculated by Shopify (POST /v1/shopify/cart). The app never calculates a
   discount or a payable total itself: it shows Shopify's subtotal, each discount Shopify applied (with its kind) and
   Shopify's total. Without Shopify's pricing only an estimate is shown, labelled as one. */

/** "Automatic discount YWPL1000" / "Coupon code SAVE10": the store's slab discounts are automatic even though
    their titles look like codes, so the customer is never told to enter a code that isn't needed. */
export const discountLabel = (d) =>
  d?.kind === "code" ? `Coupon code ${d.title}` : d?.kind === "custom" ? d.title : `Automatic discount ${d?.title ?? ""}`.trim();

/** One line explaining how the discounts are applied (no codes to enter for automatic ones). */
export const discountNote = (discounts) => {
  if (!discounts?.length) return "No store discount applies to these products at this amount.";
  return discounts.every((d) => d.kind !== "code")
    ? "Applied automatically by yuriwoori.com at checkout — no coupon code needed."
    : "Includes the coupon code shown, as applied by yuriwoori.com.";
};

/** The slab sentence, only from a verified slab summary (Shopify's pricing of this cart matched it). */
export const slabHint = (slabs, money) => {
  if (!slabs?.verified) return null;
  const current = slabs.current ? `This order is in the ${money(slabs.current.min_subtotal)}+ slab (${money(slabs.current.amount)} off).` : "";
  const next = slabs.next && slabs.add_for_next != null
    ? `Add ${money(slabs.add_for_next)} more to reach ${money(slabs.next.min_subtotal)} and get ${money(slabs.next.amount)} off instead (${slabs.next.title}, automatic).`
    : "";
  return [current, next].filter(Boolean).join(" ") || null;
};

/** One of each routine product that the live store can sell: [{variant_id, quantity: 1}] (duplicates merged). */
export const routineLines = (handles, byHandle) => {
  const seen = new Set();
  const lines = [];
  for (const h of handles) {
    const live = byHandle?.[h];
    if (!live?.variant_id || live.available === false || live.price == null || seen.has(live.variant_id)) continue;
    seen.add(live.variant_id);
    lines.push({ variant_id: live.variant_id, quantity: 1 });
  }
  return lines;
};

/** Sum of the live prices of those lines: an ESTIMATE before discounts, shown only when Shopify can't price them. */
export const estimateBeforeDiscounts = (lines, byHandle) => {
  const price = new Map(Object.values(byHandle ?? {}).filter((p) => p?.variant_id).map((p) => [p.variant_id, p.price]));
  return Math.round(lines.reduce((s, l) => s + (price.get(l.variant_id) ?? 0) * l.quantity, 0) * 100) / 100;
};

/** What a price total area may show:
    "shopify"     - Shopify's own pricing of exactly these lines (subtotal, discounts, total);
    "calculating" - asking Shopify now;
    "estimate"    - Shopify couldn't price the cart, but every price was confirmed live just now: an estimate
                    before discounts, labelled as one;
    "unavailable" - neither Shopify's pricing nor confirmed live prices: no amount is shown at all, so saved or
                    stale prices are never presented as a total. */
export const priceState = ({ shopify, quoteStatus, pricesConfirmed }) =>
  shopify ? "shopify" : quoteStatus === "loading" || quoteStatus === "idle" ? "calculating" : pricesConfirmed ? "estimate" : "unavailable";

/** Shown wherever Shopify's pricing is still loading or unavailable: no amount is presented as the final price. */
export const FINAL_PRICE_UNAVAILABLE = "Final price unavailable—verify at Shopify checkout.";

/** Shipping and taxes are not part of Shopify's cart pricing here: they are only known at Shopify checkout. */
export const SHIPPING_TAXES_NOTE = "Calculated at Shopify checkout";

/** Shopify's quote, only if it was made for exactly the current lines: a slower answer for an earlier cart
    (out of order) is ignored, never shown over newer prices. quote: { key, status, data }. */
export const currentQuote = (quote, key) => (quote && key && quote.key === key && quote.status === "ready" ? quote.data : null);
