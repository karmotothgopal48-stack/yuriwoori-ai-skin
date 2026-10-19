"""
Check STORE_DISCOUNT_SLABS against Shopify's own discount engine. For every configured slab it builds two anonymous
Shopify carts (never checked out) from live store prices: one rupee below the threshold and exactly at it, and checks
that Shopify applies the previous slab / this slab (automatic discount, same title and amount). Run from backend/:

    python scripts/check_discount_slabs.py

Exit code 0 when every boundary matches. The app also checks every priced cart at runtime and hides the slab table
whenever Shopify's result differs, so a stale setting is never shown to customers.
"""

import os
import sys

sys.path.append(os.getcwd())

from app.services import shopify_cart, shopify_client  # noqa: E402
from app.services.live_catalogue import get_catalogue  # noqa: E402


def exact_cart(target: int, items: dict[int, int], max_qty: int = 12):
    """Fewest-lines combination of whole-rupee live prices (quantity <= max_qty each) summing exactly to target."""
    prices = sorted(items)
    best = {0: []}
    for amount in range(1, target + 1):
        for price in prices:
            prev = best.get(amount - price) if price <= amount else None
            if prev is not None and prev.count(price) < max_qty and (amount not in best or len(prev) + 1 < len(best[amount])):
                best[amount] = prev + [price]
    combo = best.get(target)
    return None if combo is None else [{"variant_id": items[p], "quantity": combo.count(p)} for p in sorted(set(combo))]


def main() -> int:
    slabs = shopify_cart.configured_slabs()
    if not slabs:
        print("STORE_DISCOUNT_SLABS is empty or invalid: nothing to check (the app then shows only Shopify's applied discount).")
        return 1
    items = {}
    for p in get_catalogue().products:
        if p.available and p.variant_id and p.price and float(p.price).is_integer():
            items.setdefault(int(p.price), p.variant_id)
    ok = True
    for i, slab in enumerate(slabs):
        below = slabs[i - 1] if i else None
        for target, expected in ((int(slab["min_subtotal"]) - 1, below), (int(slab["min_subtotal"]), slab)):
            lines = exact_cart(target, items)
            if lines is None:
                print(f"  {target}: no exact cart from live prices (skipped)")
                continue
            quote = shopify_cart.quote(lines)
            applied = [(d["title"], d["amount"]) for d in quote["discounts"] if d["kind"] == "automatic"]
            want = [(expected["title"], expected["amount"])] if expected else []
            match = applied == want and quote["subtotal"] == target
            ok &= match
            configured = "" if match else f" (configured: {want or 'nothing'})"
            print(f"  [{'ok' if match else 'MISMATCH'}] subtotal {quote['subtotal']:.0f}: Shopify applied {applied or 'nothing'}{configured}")
    print("All configured slabs match Shopify." if ok else "Some slabs don't match Shopify: fix STORE_DISCOUNT_SLABS.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
