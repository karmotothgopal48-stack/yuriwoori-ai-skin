/* Cart UI: price display, Add to cart / quantity stepper (used on routine product cards), the header
   cart button and the cart drawer. All amounts come from the live store data held in the cart. */
import { useEffect, useRef } from "react";
import { FINAL_PRICE_UNAVAILABLE, SHIPPING_TAXES_NOTE, discountLabel, discountNote, priceState, slabHint } from "../services/pricing";
import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, Minus, Plus, ShoppingBag, Trash2, X } from "lucide-react";
import { formatPrice, useCart } from "../services/cart";
import { ProductImage } from "./ProductCard";

/** Current price, the original price struck through and the discount, when the store has one. */
export function Price({ price, compareAt, discount, size = "md" }) {
  if (price == null) return null;
  return (
    <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
      <span className={`font-semibold text-[#004647] tabular-nums ${size === "sm" ? "text-[14px]" : "text-[16px]"}`}>{formatPrice(price)}</span>
      {compareAt != null && <span className="text-[12px] text-ink-soft/70 line-through tabular-nums"><span className="sr-only">Original price </span>{formatPrice(compareAt)}</span>}
      {discount != null && <span className="rounded-full bg-mist px-2 py-0.5 text-[10px] font-semibold tracking-wide text-[#004647]">{discount}% off</span>}
    </p>
  );
}

/** − qty + control. */
export function QtyStepper({ qty, onChange, label }) {
  const btn = "flex h-9 w-9 items-center justify-center rounded-full text-jade transition-colors hover:bg-mist focus-visible:outline-2 focus-visible:outline-jade";
  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-jade-line bg-white px-1" role="group" aria-label={`Quantity of ${label}`}>
      <button type="button" className={btn} onClick={() => onChange(qty - 1)} aria-label={qty === 1 ? `Remove ${label} from cart` : `Decrease quantity of ${label}`}><Minus size={15} aria-hidden="true" /></button>
      <span className="min-w-[1.5rem] text-center text-sm font-semibold tabular-nums text-[#004647]" aria-live="polite">{qty}</span>
      <button type="button" className={btn} onClick={() => onChange(qty + 1)} aria-label={`Increase quantity of ${label}`}><Plus size={15} aria-hidden="true" /></button>
    </div>
  );
}

/** "Add to cart" until the product is in the cart, then the quantity stepper (shared across the page). */
export function AddToCart({ product, storeUrl }) {
  const { add, qtyOf, setQty } = useCart();
  if (!product?.variant_id) return null;
  if (!product.available) return <span className="text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-soft">Currently unavailable</span>;
  const qty = qtyOf(product.variant_id);
  if (qty > 0) return <QtyStepper qty={qty} label={product.title} onChange={(n) => setQty(product.variant_id, n)} />;
  return (
    <button type="button" onClick={() => add(product, storeUrl)}
      className="inline-flex min-h-[40px] items-center gap-2 rounded-pill bg-jade px-5 text-[13px] font-semibold tracking-wide text-cream transition-colors hover:bg-[#004647] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-jade">
      <ShoppingBag size={15} aria-hidden="true" /> Add to cart
    </button>
  );
}

/** Header cart button with the item count. */
export function CartButton() {
  const { count, setOpen } = useCart();
  return (
    <button type="button" onClick={() => setOpen(true)} aria-label={`Open cart, ${count} item${count === 1 ? "" : "s"}`}
      className="relative rounded-full p-2 text-ink-soft transition-colors hover:bg-mist hover:text-ink focus-visible:outline-2 focus-visible:outline-jade">
      <ShoppingBag size={20} strokeWidth={1.5} aria-hidden="true" />
      {count > 0 && (
        <span className="absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-jade px-1 text-[10px] font-semibold text-cream tabular-nums">{count}</span>
      )}
    </button>
  );
}

/** Slide-in cart: items, quantities, remove, subtotal and checkout on yuriwoori.com. */
export function CartDrawer() {
  const { items, subtotal, checkoutUrl, setQty, remove, open, setOpen, priceCheck, shopify, quoteStatus } = useCart();
  // what the total area may show: Shopify's pricing, an estimate from prices confirmed live just now, or nothing
  const pricing = priceState({ shopify, quoteStatus, pricesConfirmed: priceCheck === "current" });
  const closeRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = overflow; opener?.focus?.(); };
  }, [open, setOpen]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50">
          <motion.div className="absolute inset-0 bg-[#0f2b2a]/35 backdrop-blur-[2px]" onClick={() => setOpen(false)}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} aria-hidden="true" />
          <motion.aside role="dialog" aria-modal="true" aria-labelledby="cart-title"
            className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col bg-cream shadow-float"
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}>
            <header className="flex items-center justify-between border-b border-hairline bg-white px-5 py-4">
              <h2 id="cart-title" className="font-display text-[22px] text-[#004647]">Your cart</h2>
              <button ref={closeRef} type="button" onClick={() => setOpen(false)} aria-label="Close cart"
                className="rounded-full p-2 text-ink-soft hover:bg-mist hover:text-ink focus-visible:outline-2 focus-visible:outline-jade"><X size={20} aria-hidden="true" /></button>
            </header>

            {items.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 px-8 text-center text-ink-soft">
                <ShoppingBag size={28} className="text-jade-line" aria-hidden="true" />
                <p className="font-display text-[20px] text-[#004647]">Your cart is empty</p>
                <p className="text-[13px]">Add products from your morning or evening routine.</p>
              </div>
            ) : (
              <>
                <ul className="flex-1 divide-y divide-sage-light/60 overflow-y-auto px-5">
                  {items.map((i) => (
                    <li key={i.variantId} className="flex gap-4 py-4">
                      <ProductImage product={{ name: i.title, image: i.image }} bg="bg-white" className="h-20 w-20 shrink-0 rounded-2xl border border-hairline" />
                      <div className="min-w-0 flex-1">
                        <a href={i.url} target="_blank" rel="noreferrer" className="line-clamp-2 text-[14px] font-medium leading-snug text-[#004647] hover:underline">
                          {i.title.replace(/^Yuri Woori /, "")}
                        </a>
                        <div className="mt-1">
                          {i.unavailable
                            ? <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-soft">No longer available</p>
                            : <Price price={i.price} compareAt={i.compareAt} size="sm" />}
                        </div>
                        <div className="mt-2 flex items-center justify-between gap-2">
                          <QtyStepper qty={i.qty} label={i.title} onChange={(n) => setQty(i.variantId, n)} />
                          <button type="button" onClick={() => remove(i.variantId)} aria-label={`Remove ${i.title}`}
                            className="rounded-full p-2 text-ink-soft hover:bg-mist hover:text-[#7d4f45] focus-visible:outline-2 focus-visible:outline-jade"><Trash2 size={16} aria-hidden="true" /></button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
                <footer className="border-t border-hairline bg-white px-5 py-5">
                  {pricing === "shopify" ? (
                    // Shopify's own pricing of this cart: subtotal, each discount it applies, total
                    <dl className="grid gap-1.5 text-[14px]" aria-live="polite">
                      <div className="flex items-baseline justify-between text-ink-soft">
                        <dt>Subtotal</dt><dd className="tabular-nums">{formatPrice(shopify.subtotal)}</dd>
                      </div>
                      {shopify.discounts.map((d) => (
                        <div key={`${d.kind}-${d.title}`} className="flex items-baseline justify-between text-[#004647]">
                          <dt>{discountLabel(d)}</dt><dd className="tabular-nums">−{formatPrice(d.amount)}</dd>
                        </div>
                      ))}
                      <div className="flex items-baseline justify-between text-ink-soft">
                        <dt>Shipping &amp; taxes</dt><dd className="text-[12px]">{SHIPPING_TAXES_NOTE}</dd>
                      </div>
                      <div className="mt-1 flex items-baseline justify-between border-t border-sage-light pt-2">
                        <dt className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink-soft">Total payable (before shipping)</dt>
                        <dd className="font-display text-[24px] text-[#004647] tabular-nums">{formatPrice(shopify.total)}</dd>
                      </div>
                      <p className="text-[11px] text-ink-soft">{discountNote(shopify.discounts)}</p>
                      {slabHint(shopify.slabs, formatPrice) && (
                        <p className="mt-1 rounded-lg bg-mist/60 px-2.5 py-1.5 text-[11px] leading-relaxed text-[#004647]">{slabHint(shopify.slabs, formatPrice)}</p>)}
                    </dl>
                  ) : pricing === "estimate" ? (
                    // Shopify couldn't price the cart, but every line's price was confirmed live just now
                    <div className="grid gap-1.5" role="status">
                      <p className="text-[14px] font-semibold text-ink">{FINAL_PRICE_UNAVAILABLE}</p>
                      <div className="flex items-baseline justify-between">
                        <span className="text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-soft">Subtotal (estimate, before discounts)</span>
                        <span className="text-[18px] text-ink tabular-nums">{formatPrice(subtotal)}</span>
                      </div>
                    </div>
                  ) : pricing === "calculating" ? (
                    <p className="text-[14px] text-ink-soft" role="status">{FINAL_PRICE_UNAVAILABLE} (calculating on yuriwoori.com…)</p>
                  ) : (
                    // neither Shopify's pricing nor confirmed live prices: no amount, so saved prices are never shown as a total
                    <p className="text-[14px] font-semibold text-ink" role="status">{FINAL_PRICE_UNAVAILABLE}</p>
                  )}
                  <p className="mt-1 text-[11px] leading-relaxed text-ink-soft/80" aria-live="polite">
                    {priceCheck === "checking" ? "Checking current prices on yuriwoori.com… "
                      : priceCheck === "error" ? "Current prices couldn't be checked right now. "
                      : priceCheck === "stale" ? "yuriwoori.com couldn't be reached just now, so these are its most recent prices. "
                      : shopify ? "Prices and discounts calculated by yuriwoori.com (Shopify) for this cart. "
                      : quoteStatus === "loading" ? "Calculating discounts on yuriwoori.com… "
                      : quoteStatus === "error" ? "Discounts couldn't be calculated right now; any that apply are added at checkout. "
                      : "Prices from yuriwoori.com. "}
                    Shipping, and the final amount, are shown at checkout.
                  </p>
                  <a href={checkoutUrl ?? undefined} target="_blank" rel="noreferrer" aria-disabled={!checkoutUrl}
                    className="mt-4 inline-flex min-h-[50px] w-full items-center justify-center gap-2 rounded-pill bg-jade text-[15px] font-semibold tracking-wide text-cream transition-colors hover:bg-[#004647] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-jade">
                    Proceed to checkout <ExternalLink size={15} aria-hidden="true" />
                  </a>
                </footer>
              </>
            )}
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  );
}
