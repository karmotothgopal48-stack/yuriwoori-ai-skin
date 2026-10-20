/* One cart for the whole skin-analysis app. Items are keyed by Shopify variant ID, so the same product
   added from the Morning and the Evening routine becomes one line with a higher quantity.
   Product details come from the live YuriWoori store (services/liveProducts.js) and are re-checked against it
   whenever the cart is opened; checkout opens the store's own cart page
   (https://yuriwoori.com/cart/<variant>:<qty>,...?storefront=true), where final prices and availability are
   confirmed. The cart is kept in this browser only (localStorage, guarded). */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { currentQuote } from "./pricing";
import { addItem, cartCount, cartLines, cartSubtotal, checkoutUrl, linesKey, refreshItems, removeItem, setItemQty, validItems } from "./cartLogic";
import { fetchLiveProducts } from "./liveProducts";
import { api } from "./api";

const KEY = "yw_cart";
const read = () => { try { return validItems(JSON.parse(localStorage.getItem(KEY))); } catch { return []; } };
const write = (items) => { try { localStorage.setItem(KEY, JSON.stringify(items)); } catch { /* storage unavailable: cart lasts this page */ } };

const CartContext = createContext(null);

export function CartProvider({ children }) {
  const [items, setItems] = useState(read);
  const [open, setOpen] = useState(false);
  // "idle" | "checking" | "current" (live prices) | "stale" (the store's last copy) | "error" (couldn't check)
  const [priceCheck, setPriceCheck] = useState("idle");
  useEffect(() => { write(items); }, [items]);

  // Opening the cart re-checks every saved line against the live store, so prices and stock are current.
  const handleKey = [...new Set(items.map((i) => i.handle))].sort().join(",");
  useEffect(() => {
    if (!open || !handleKey) return;
    let alive = true;
    setPriceCheck("checking");
    fetchLiveProducts(handleKey.split(","))
      .then((live) => {
        if (!alive) return;
        setItems((cur) => refreshItems(cur, live.byHandle));
        setPriceCheck(live.stale ? "stale" : "current");
      })
      .catch(() => { if (alive) setPriceCheck("error"); });
    return () => { alive = false; };
  }, [open, handleKey]);

  // Shopify prices the open cart (POST /v1/shopify/cart): its subtotal, the discounts it applies (e.g. the
  // store's automatic discounts) and its total, plus the checkout URL of that same cart. The app never
  // computes discounts itself. { key, status: "loading" | "ready" | "error", data }
  const [quote, setQuote] = useState({ key: "", status: "idle", data: null });
  const key = linesKey(items);
  useEffect(() => {
    if (!open || !key || priceCheck === "checking") return;
    let alive = true;
    setQuote({ key, status: "loading", data: null });
    api("/shopify/cart", { method: "POST", body: { lines: cartLines(items) }, auth: false })
      .then((data) => { if (alive) setQuote({ key, status: "ready", data }); })
      .catch(() => { if (alive) setQuote({ key, status: "error", data: null }); });
    return () => { alive = false; };
  }, [open, key, priceCheck]); // `key` stands for `items`: re-price only when the lines change

  /** Add one of a live product (from /catalogue/live); merges with an existing line (cartLogic.addItem). */
  const add = useCallback((p, storeUrl) => setItems((cur) => addItem(cur, p, storeUrl)), []);
  const setQty = useCallback((variantId, qty) => setItems((cur) => setItemQty(cur, variantId, qty)), []);
  const remove = useCallback((variantId) => setItems((cur) => removeItem(cur, variantId)), []);

  const value = useMemo(() => {
    const qtyOf = (variantId) => items.find((i) => i.variantId === variantId)?.qty ?? 0;
    // Only a quote for exactly the current lines is shown; its checkout URL keeps Shopify's cart and discounts.
    const shopify = currentQuote(quote, key);
    const quoteStatus = !key ? "idle" : quote.key === key ? quote.status : "loading";
    return {
      items, count: cartCount(items), subtotal: cartSubtotal(items), qtyOf, add, setQty, remove, open, setOpen, priceCheck,
      shopify, quoteStatus, checkoutUrl: shopify?.checkout_url ?? checkoutUrl(items),
    };
  }, [items, add, setQty, remove, open, priceCheck, quote, key]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export const useCart = () => useContext(CartContext);

/** "₹855" — the store sells in Indian rupees, as the existing catalogue does. */
export const formatPrice = (n) => (n == null ? "" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`);
