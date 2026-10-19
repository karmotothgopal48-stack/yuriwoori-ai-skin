import { test } from "node:test";
import assert from "node:assert/strict";
import { addItem, cartCount, cartLines, cartSubtotal, checkoutUrl, linesKey, refreshItems, removeItem, setItemQty, validItems, variantNumber } from "../src/services/cartLogic.js";

const STORE = "https://yuriwoori.com";
const toner = { variant_id: 111, handle: "toner", title: "Toner", price: 855, compare_at_price: 950, url: `${STORE}/products/toner` };
const cream = { variant_id: 222, handle: "cream", title: "Cream", price: 1200.5, url: `${STORE}/products/cream` };

test("add to cart adds the product once", () => {
  const items = addItem([], toner, STORE);
  assert.equal(items.length, 1);
  assert.equal(items[0].qty, 1);
  assert.equal(items[0].variantId, 111);
});

test("adding the same product again increments quantity, no duplicate line", () => {
  let items = addItem([], toner, STORE);
  items = addItem(items, toner, STORE);
  items = addItem(items, cream, STORE);
  assert.equal(items.length, 2);
  assert.equal(items.find((i) => i.variantId === 111).qty, 2);
  assert.equal(cartCount(items), 3);
  assert.equal(cartSubtotal(items), 2910.5);
  assert.equal(checkoutUrl(items), `${STORE}/cart/111:2,222:1?storefront=true`);
});

test("products without a variant or price are not added", () => {
  assert.deepEqual(addItem([], { ...toner, variant_id: null }, STORE), []);
  assert.deepEqual(addItem([], { ...toner, price: null }, STORE), []);
});

test("quantity changes and removal", () => {
  let items = addItem(addItem([], toner, STORE), cream, STORE);
  items = setItemQty(items, 111, 4);
  assert.equal(items[0].qty, 4);
  assert.equal(setItemQty(items, 111, 0).length, 1);
  assert.equal(removeItem(items, 222).length, 1);
  assert.equal(checkoutUrl([]), null);
});

test("malformed saved carts are dropped", () => {
  assert.deepEqual(validItems(null), []);
  assert.deepEqual(validItems([{ variantId: 1, qty: 1, price: 10 }, { variantId: 2, qty: 0, price: 10 }, { qty: 1, price: 1 }, null]).length, 1);
});

// /catalogue/live entries, as the store reports them now
const live = (product, variant) => ({ [product.handle]: { handle: product.handle, title: product.title, url: product.url, image_url: null, variants: [variant] } });

test("saved lines take the store's current price and original price", () => {
  const items = addItem(addItem([], toner, STORE), cream, STORE);
  const now = { ...live(toner, { id: 111, price: 799, compare_at_price: 950, available: true }),
    ...live(cream, { id: 222, price: 1300, compare_at_price: 1300, available: true }) };
  const fresh = refreshItems(items, now);
  assert.deepEqual(fresh.map((i) => [i.price, i.compareAt, i.unavailable]), [[799, 950, false], [1300, null, false]]);
  assert.equal(cartSubtotal(fresh), 2099);
});

test("lines the store no longer sells, or has sold out, are kept but not checked out", () => {
  const items = addItem(addItem([], toner, STORE), cream, STORE);
  const fresh = refreshItems(items, live(cream, { id: 222, price: 1200.5, available: false })); // toner gone, cream sold out
  assert.equal(fresh.length, 2);
  assert.ok(fresh.every((i) => i.unavailable));
  assert.equal(cartSubtotal(fresh), 0);
  assert.equal(checkoutUrl(fresh), null);

  const partly = refreshItems(items, live(toner, { id: 111, price: 855, available: true }));
  assert.equal(checkoutUrl(partly), `${STORE}/cart/111:1?storefront=true`);
});

test("a line whose variant is no longer offered is unavailable", () => {
  const items = addItem([], toner, STORE);
  assert.equal(refreshItems(items, live(toner, { id: 999, price: 855, available: true }))[0].unavailable, true);
});

test("adding a product again brings its line up to date", () => {
  const stale = refreshItems(addItem([], toner, STORE), {});
  const again = addItem(stale, { ...toner, price: 700 }, STORE);
  assert.deepEqual([again[0].qty, again[0].price, again[0].unavailable], [2, 700, false]);
});

test("Shopify prices exactly the buyable lines, and a quote belongs to one cart content", () => {
  let items = addItem(addItem([], toner, STORE), cream, STORE);
  items = setItemQty(items, 222, 3);
  assert.deepEqual(cartLines(items), [{ variant_id: 111, quantity: 1 }, { variant_id: 222, quantity: 3 }]);
  const key = linesKey(items);
  assert.equal(key, "111:1,222:3");
  assert.notEqual(linesKey(setItemQty(items, 222, 2)), key); // a quantity change needs a new Shopify quote
  const soldOut = refreshItems(items, live(toner, { id: 111, price: 855, available: true })); // cream gone
  assert.deepEqual(cartLines(soldOut), [{ variant_id: 111, quantity: 1 }]);
});


test("saved lines for the same variant in different ID forms become one line, so nothing is counted twice", () => {
  assert.equal(variantNumber("gid://shopify/ProductVariant/44562254463010"), 44562254463010);
  assert.equal(variantNumber("44562254463010"), 44562254463010);
  assert.equal(variantNumber("not-an-id"), null);
  const saved = [
    { variantId: 44562254463010, handle: "bubble-anti-aging-toner", qty: 1, price: 765 },
    { variantId: "gid://shopify/ProductVariant/44562254463010", handle: "bubble-anti-aging-toner", qty: 1, price: 765 },
    { variantId: "44562254004258", handle: "rice-facial-deep-cleansing-foam", qty: 1, price: 855 },
    { variantId: "junk", handle: "x", qty: 1, price: 400 },  // malformed: dropped, never priced
  ];
  const items = validItems(saved);
  assert.deepEqual(items.map((i) => [i.variantId, i.qty]), [[44562254463010, 2], [44562254004258, 1]]);
  assert.deepEqual(cartLines(items), [{ variant_id: 44562254463010, quantity: 2 }, { variant_id: 44562254004258, quantity: 1 }]);
});

test("the reported four products: the cart subtotal is the live prices, and only variant + quantity go to Shopify", () => {
  const live = (id, price) => ({ variant_id: id, price, compare_at_price: null, title: "t", url: "u", image_url: null, handle: `h${id}` });
  let items = [];
  for (const [id, price] of [[44562254004258, 855], [44562254463010, 765], [44562254790690, 1350], [44562255249442, 2025]]) {
    items = addItem(items, live(id, price), "https://yuriwoori.com");
  }
  items = addItem(items, live(44562254463010, 765), "https://yuriwoori.com");  // added twice: a quantity, not a hidden second line
  assert.equal(items.length, 4);
  assert.equal(cartSubtotal(items), 4995 + 765);
  assert.ok(cartLines(items).every((l) => Object.keys(l).join() === "variant_id,quantity"));  // no local price sent
});

test("Shopify's current variant data replaces saved prices; a variant no longer sold leaves the total and checkout", () => {
  const saved = [
    { variantId: 11, handle: "foam", qty: 1, price: 900, title: "old", url: "u", storeUrl: STORE },       // saved at an older price
    { variantId: 22, handle: "toner", qty: 2, price: 765, title: "t", url: "u", storeUrl: STORE },
    { variantId: 33, handle: "patch", qty: 1, price: 1350, title: "p", url: "u", storeUrl: STORE },     // variant changed on Shopify
  ];
  const byHandle = {
    foam: { title: "Rice Foam", url: "u", image_url: null, variants: [{ id: 11, price: 855, compare_at_price: 950, available: true }] },
    toner: { title: "Toner", url: "u", image_url: null, variants: [{ id: 22, price: 765, compare_at_price: 850, available: true }] },
    patch: { title: "Patch", url: "u", image_url: null, variants: [{ id: 34, price: 1350, compare_at_price: 1500, available: true }] },
  };
  const items = refreshItems(saved, byHandle);
  assert.equal(items[0].price, 855);                        // Shopify's price, not the saved 900
  assert.equal(items[2].unavailable, true);                 // its variant isn't sold any more: not priced, not checked out
  assert.equal(cartSubtotal(items), 855 + 2 * 765);
  assert.deepEqual(cartLines(items).map((l) => l.variant_id), [11, 22]);
  assert.ok(!checkoutUrl(items).includes("33:"));
});

test("changing a quantity changes the lines Shopify is asked to price", () => {
  const items = [{ variantId: 11, handle: "foam", qty: 1, price: 855, storeUrl: STORE }];
  const more = setItemQty(items, 11, 3);
  assert.notEqual(linesKey(items), linesKey(more));
  assert.deepEqual(cartLines(more), [{ variant_id: 11, quantity: 3 }]);
  assert.deepEqual(setItemQty(items, 11, 0), []);
});
