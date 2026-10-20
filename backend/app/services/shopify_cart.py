"""
The customer's cart, priced by Shopify. The app never calculates discounts or totals itself: the lines
(variant + quantity) are sent to Shopify's Storefront API (cartCreate), and Shopify returns the subtotal,
every discount it applies (e.g. the store's automatic discounts, with their own titles), the total and the
checkout URL for that same cart — so the checkout opens with the same lines and discounts.

Shopify's cart total is before shipping and any checkout-only adjustments; the checkout shows the final amount.

Each discount keeps its kind: "automatic" (Shopify applies it with no code; the store's slab discounts are titled
like codes, e.g. YWPL1000, but need no code), "code" (a coupon code on the cart) or "custom". The store's slab table
(STORE_DISCOUNT_SLABS) is returned only when Shopify applied exactly the slab it predicts for this cart.
"""
import logging


from app.core.config import settings
from app.services import shopify_client

logger = logging.getLogger(__name__)


def _money(value) -> float | None:
    try:
        return round(float((value or {}).get("amount")), 2)
    except (TypeError, ValueError):
        return None


def _kind(allocation: dict) -> str:
    # the cart query asks for `code` only on CartCodeDiscountAllocation and `title` on the automatic/custom ones
    if allocation.get("code"):
        return "code"
    return "custom" if allocation.get("__typename") == "CartCustomDiscountAllocation" else "automatic"


def _discounts(allocations: list[dict]) -> list[dict]:
    """Shopify's discount allocations grouped by discount (title or code) and kind, largest first."""
    totals: dict[tuple[str, str], float] = {}
    for a in allocations or []:
        key = (a.get("title") or a.get("code") or "Discount", _kind(a))
        totals[key] = totals.get(key, 0.0) + (_money(a.get("discountedAmount")) or 0.0)
    return [{"title": t, "kind": k, "amount": round(v, 2)} for (t, k), v in sorted(totals.items(), key=lambda kv: -kv[1]) if v > 0]


def configured_slabs() -> list[dict]:
    """STORE_DISCOUNT_SLABS -> [{min_subtotal, amount, title}] by threshold (an invalid entry disables them all)."""
    slabs = []
    for part in filter(None, (x.strip() for x in settings.store_discount_slabs.split(","))):
        try:
            minimum, amount, title = part.split(":", 2)
            slabs.append({"min_subtotal": float(minimum), "amount": float(amount), "title": title.strip()})
        except ValueError:
            logger.warning("STORE_DISCOUNT_SLABS has an invalid entry: slabs are not shown")
            return []
    return sorted(slabs, key=lambda s: s["min_subtotal"])


def slab_summary(subtotal: float | None, discounts: list[dict]) -> dict | None:
    """The slab table for this cart, only if Shopify's automatic discounts on it are exactly what the table predicts
    (same title, same amount, no other automatic discount). Otherwise {"verified": False}: nothing is claimed."""
    table = configured_slabs()
    if not table or subtotal is None:
        return None
    current = next((s for s in reversed(table) if subtotal >= s["min_subtotal"]), None)
    expected = [(current["title"], current["amount"])] if current else []
    applied = [(d["title"], d["amount"]) for d in discounts if d.get("kind") == "automatic"]
    if applied != expected:
        logger.warning("Configured discount slabs don't match Shopify's pricing of a cart: slabs not shown")
        return {"verified": False}
    upcoming = next((s for s in table if s["min_subtotal"] > subtotal), None)
    return {"verified": True, "table": table, "current": current, "next": upcoming,
            "add_for_next": round(upcoming["min_subtotal"] - subtotal, 2) if upcoming else None}


def describe(cart: dict) -> dict:
    """A Storefront cart -> the CartQuoteResponse fields."""
    line_allocations = []
    lines = []
    for node in (cart.get("lines") or {}).get("nodes") or []:
        variant = node.get("merchandise") or {}
        cost = node.get("cost") or {}
        line_allocations += node.get("discountAllocations") or []
        lines.append({
            "variant_id": shopify_client.gid_number(variant.get("id")),
            "handle": (variant.get("product") or {}).get("handle"),
            "title": (variant.get("product") or {}).get("title"),
            "quantity": node.get("quantity"),
            "unit_price": _money(cost.get("amountPerQuantity")),
            "compare_at_price": _money(cost.get("compareAtAmountPerQuantity")),
            "subtotal": _money(cost.get("subtotalAmount")),
            "total": _money(cost.get("totalAmount")),
        })
    total_cost = cart.get("cost") or {}
    discounts = _discounts((cart.get("discountAllocations") or []) + line_allocations)
    subtotal = _money(total_cost.get("subtotalAmount"))
    return {
        "cart_id": cart.get("id"),
        "checkout_url": cart.get("checkoutUrl"),
        "currency": (total_cost.get("subtotalAmount") or {}).get("currencyCode") or "INR",
        "subtotal": subtotal,
        "discounts": discounts,
        "slabs": slab_summary(subtotal, discounts),
        "total": _money(total_cost.get("totalAmount")),
        "total_quantity": cart.get("totalQuantity"),
        "lines": lines,
        "warnings": [w.get("message") for w in cart.get("warnings") or [] if w.get("message")],
    }


def quote(lines: list[dict]) -> dict:
    """lines: [{"variant_id": int, "quantity": int}] -> Shopify's priced cart (CartQuoteResponse fields)."""
    cart = shopify_client.create_cart(
        [{"merchandiseId": shopify_client.variant_gid(l["variant_id"]), "quantity": l["quantity"]} for l in lines])
    return describe(cart)
