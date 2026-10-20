/* Pure cart rules (no React, so they can be unit-tested with node --test). Items are keyed by Shopify
   variant ID: adding a product that is already in the cart raises its quantity instead of adding a line. */

const lineFrom = (product) => ({
  title: product.title, image: product.image_url ?? null, price: product.price,
  compareAt: product.compare_at_price ?? null, url: product.url, unavailable: false,
});

/** Add one of a live product (from /catalogue/live). Products without a variant or price can't be added.
    An existing line takes the product's current details along with the extra unit. */
export function addItem(items, product, storeUrl) {
  if (!product?.variant_id || product.price == null) return items;
  const found = items.find((i) => i.variantId === product.variant_id);
  if (found) return items.map((i) => (i.variantId === product.variant_id ? { ...i, ...lineFrom(product), qty: i.qty + 1 } : i));
  return [...items, { variantId: product.variant_id, handle: product.handle, storeUrl, qty: 1, ...lineFrom(product) }];
}

/** Saved lines re-checked against the live store (`byHandle` from /catalogue/live): current title, image, price
    and original price of the line's own variant. A line whose product or variant is no longer sold, or is sold
    out, is kept but marked unavailable: it is left out of the subtotal and checkout. */
export function refreshItems(items, byHandle) {
  return items.map((i) => {
    const live = byHandle[i.handle];
    const variant = live?.variants?.find((v) => v.id === i.variantId);
    if (!variant || !variant.available || variant.price == null) return { ...i, unavailable: true };
    const compareAt = variant.compare_at_price != null && variant.compare_at_price > variant.price ? variant.compare_at_price : null;
    return { ...i, title: live.title, image: live.image_url ?? i.image, url: live.url, price: variant.price, compareAt, unavailable: false };
  });
}

const buyable = (items) => items.filter((i) => !i.unavailable);

/** The lines Shopify prices (POST /v1/shopify/cart): every buyable line's variant and quantity. */
export const cartLines = (items) => buyable(items).map((i) => ({ variant_id: i.variantId, quantity: i.qty }));

/** Identifies the cart contents, so a Shopify quote is only used for exactly the cart it was made for. */
export const linesKey = (items) => cartLines(items).map((l) => `${l.variant_id}:${l.quantity}`).sort().join(",");

/** Set a line's quantity; 0 or less removes it. */
export const setItemQty = (items, variantId, qty) =>
  (qty <= 0 ? items.filter((i) => i.variantId !== variantId) : items.map((i) => (i.variantId === variantId ? { ...i, qty } : i)));

export const removeItem = (items, variantId) => items.filter((i) => i.variantId !== variantId);

export const cartCount = (items) => items.reduce((n, i) => n + i.qty, 0);
export const cartSubtotal = (items) => Math.round(buyable(items).reduce((s, i) => s + (i.price ?? 0) * i.qty, 0) * 100) / 100;

/** yuriwoori.com's own Shopify cart page, pre-filled: <store>/cart/<variant>:<qty>,...?storefront=true
    (`storefront=true` lands on the store's /cart page, whose Check out button opens Shopify checkout). */
export function checkoutUrl(items) {
  const lines = buyable(items);
  const storeUrl = lines[0]?.storeUrl;
  return lines.length && storeUrl ? `${storeUrl}/cart/${lines.map((i) => `${i.variantId}:${i.qty}`).join(",")}?storefront=true` : null;
}

/** A Shopify variant ID as a number, whatever form it was saved in (number, "123", "gid://shopify/ProductVariant/123"). */
export const variantNumber = (id) => {
  const n = Number(String(id ?? "").split("/").pop());
  return Number.isSafeInteger(n) && n > 0 ? n : null;
};

/** Saved carts from older sessions: well-formed lines only, variant IDs as numbers, and one line per variant
    (lines saved for the same variant in different forms are merged), so nothing is counted twice. */
export const validItems = (value) => {
  if (!Array.isArray(value)) return [];
  const merged = [];
  for (const i of value) {
    const variantId = variantNumber(i?.variantId);
    if (!variantId || !Number.isInteger(i.qty) || i.qty <= 0 || typeof i.price !== "number") continue;
    const found = merged.find((m) => m.variantId === variantId);
    if (found) found.qty += i.qty;
    else merged.push({ ...i, variantId });
  }
  return merged;
};
