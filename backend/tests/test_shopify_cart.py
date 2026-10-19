"""
The cart priced by Shopify (app/services/shopify_cart.py, POST /v1/shopify/cart). Shopify is stubbed with the
shape of a real cartCreate response for the reported four-product basket: subtotal ₹4,995, the store's
automatic discount "YWPL1000" (−₹1,000, split across lines), total ₹3,995.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import shopify_cart, shopify_client
from app.services.shopify_client import ShopifyError

BASKET = ["rice-facial-deep-cleansing-foam", "bubble-soothing-toner", "cloud-cream-korean-aqua-hyaluronic-moisture-cream",
          "real-gold-hydro-gel-eye-patch"]


def _line(handle, variant, price, compare):
    return {"id": f"gid://shopify/CartLine/{variant}", "quantity": 1,
            "merchandise": {"id": f"gid://shopify/ProductVariant/{variant}", "title": "Default Title", "product": {"handle": handle, "title": handle}},
            "cost": {"amountPerQuantity": {"amount": str(price)}, "compareAtAmountPerQuantity": {"amount": str(compare)},
                     "subtotalAmount": {"amount": str(price)}, "totalAmount": {"amount": str(price)}},
            "discountAllocations": []}


SHOPIFY_CART = {  # as Shopify returned it on 2026-10-13 (amounts and discount title verbatim)
    "id": "gid://shopify/Cart/abc", "checkoutUrl": "https://yuriwoori.com/cart/c/abc?key=k", "totalQuantity": 4,
    "cost": {"subtotalAmount": {"amount": "4995.0", "currencyCode": "INR"}, "totalAmount": {"amount": "3995.0", "currencyCode": "INR"}},
    "discountCodes": [],
    "discountAllocations": [{"discountedAmount": {"amount": a}, "title": "YWPL1000"} for a in ("270.28", "405.4", "153.15", "171.17")],
    "lines": {"nodes": [_line("real-gold-hydro-gel-eye-patch", 4, 1350, 1500), _line("cloud-cream-korean-aqua-hyaluronic-moisture-cream", 3, 2025, 2250),
                        _line("bubble-soothing-toner", 2, 765, 850), _line("rice-facial-deep-cleansing-foam", 1, 855, 950)]},
    "warnings": [],
}


def test_shopify_totals_and_discounts_are_reported_as_shopify_computed_them():
    q = shopify_cart.describe(SHOPIFY_CART)
    assert (q["subtotal"], q["total"], q["currency"]) == (4995.0, 3995.0, "INR")
    assert q["discounts"] == [{"title": "YWPL1000", "kind": "automatic", "amount": 1000.0}]  # split allocations summed, title verbatim
    assert q["checkout_url"] == "https://yuriwoori.com/cart/c/abc?key=k" and q["total_quantity"] == 4
    assert {(l["handle"], l["variant_id"], l["unit_price"], l["compare_at_price"]) for l in q["lines"]} >= {("bubble-soothing-toner", 2, 765.0, 850.0)}


def test_a_cart_without_discounts_has_none():
    cart = {**SHOPIFY_CART, "discountAllocations": [], "cost": {"subtotalAmount": {"amount": "855.0"}, "totalAmount": {"amount": "855.0"}}}
    q = shopify_cart.describe(cart)
    assert q["discounts"] == [] and q["subtotal"] == q["total"] == 855.0


def test_cart_lines_are_sent_as_storefront_variant_gids(monkeypatch):
    sent = {}

    def handler(request):
        import json
        sent.update(json.loads(request.content))
        return httpx.Response(200, json={"data": {"cartCreate": {"cart": SHOPIFY_CART, "userErrors": [], "warnings": []}}})

    monkeypatch.setattr(shopify_client, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    q = shopify_cart.quote([{"variant_id": 44562254495778, "quantity": 2}])
    assert "cartCreate(input: $input)" in sent["query"]
    assert sent["variables"] == {"input": {"lines": [{"merchandiseId": "gid://shopify/ProductVariant/44562254495778", "quantity": 2}]}}
    assert q["total"] == 3995.0


def test_shopify_user_errors_are_failures(monkeypatch):
    monkeypatch.setattr(shopify_client, "_client", lambda: httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"data": {"cartCreate": {"cart": None, "userErrors": [{"field": ["lines"], "message": "Sold out"}]}}}))))
    with pytest.raises(ShopifyError):
        shopify_cart.quote([{"variant_id": 1, "quantity": 1}])


def test_cart_endpoint_prices_only_variants_the_store_sells(monkeypatch, catalogue):
    sent = []
    monkeypatch.setattr(shopify_cart, "quote", lambda lines: (sent.append(lines), shopify_cart.describe(SHOPIFY_CART))[1])
    client = TestClient(app)
    variants = [catalogue.get(h).variant_id for h in BASKET]
    r = client.post("/v1/shopify/cart", json={"lines": [{"variant_id": v, "quantity": 1} for v in variants] + [{"variant_id": variants[0], "quantity": 1}]})
    assert r.status_code == 200 and r.json()["total"] == 3995.0 and r.json()["discounts"][0]["title"] == "YWPL1000"
    assert {l["variant_id"]: l["quantity"] for l in sent[0]}[variants[0]] == 2  # the same variant twice -> one line

    assert client.post("/v1/shopify/cart", json={"lines": [{"variant_id": 1, "quantity": 1}]}).status_code == 400  # not in the store
    assert client.post("/v1/shopify/cart", json={"lines": []}).status_code == 422
    assert client.post("/v1/shopify/cart", json={"lines": [{"variant_id": variants[0], "quantity": 0}]}).status_code == 422


def test_cart_endpoint_reports_shopify_failures(monkeypatch, catalogue):
    client = TestClient(app)
    line = {"lines": [{"variant_id": catalogue.get(BASKET[0]).variant_id, "quantity": 1}]}

    def refused(lines):
        raise ShopifyError("Shopify cart error: Sold out")
    monkeypatch.setattr(shopify_cart, "quote", refused)
    assert client.post("/v1/shopify/cart", json=line).status_code == 400

    def down(lines):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(shopify_cart, "quote", down)
    assert client.post("/v1/shopify/cart", json=line).status_code == 502


# ---------- discount kinds and the store's slabs (verified against Shopify's result for each cart) ----------

SLABS = "2500:500:YWPL500,3500:1000:YWPL1000,5500:1500:YWPL1500"  # measured against Shopify on 2026-10-19


def test_the_reported_basket_is_shopify_4995_minus_automatic_ywpl1000_equals_3995(monkeypatch):
    """The reported mismatch: the app showed the products' sum (₹4,995) while checkout showed ₹3,995. The ₹1,000 is
    Shopify's AUTOMATIC discount YWPL1000 (no code), which Shopify itself reports for this cart."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "store_discount_slabs", SLABS)
    q = shopify_cart.describe(SHOPIFY_CART)
    assert q["subtotal"] == 4995.0 and q["total"] == 3995.0
    assert q["discounts"] == [{"title": "YWPL1000", "kind": "automatic", "amount": 1000.0}]
    assert q["subtotal"] - sum(d["amount"] for d in q["discounts"]) == q["total"]  # the breakdown adds up exactly
    assert q["slabs"]["verified"] is True and q["slabs"]["current"]["title"] == "YWPL1000"
    assert q["slabs"]["next"]["title"] == "YWPL1500" and q["slabs"]["add_for_next"] == 505.0


def test_a_coupon_code_is_labelled_as_a_code_and_never_mistaken_for_the_automatic_slab(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "store_discount_slabs", SLABS)
    cart = {**SHOPIFY_CART, "discountAllocations": [
        {"__typename": "CartCodeDiscountAllocation", "discountedAmount": {"amount": "200"}, "code": "WELCOME200"},
        {"__typename": "CartAutomaticDiscountAllocation", "discountedAmount": {"amount": "1000"}, "title": "YWPL1000"}],
        "cost": {"subtotalAmount": {"amount": "4995.0", "currencyCode": "INR"}, "totalAmount": {"amount": "3795.0", "currencyCode": "INR"}}}
    q = shopify_cart.describe(cart)
    assert q["discounts"] == [{"title": "YWPL1000", "kind": "automatic", "amount": 1000.0},
                              {"title": "WELCOME200", "kind": "code", "amount": 200.0}]
    assert q["total"] == 3795.0 and q["slabs"]["verified"] is True  # the automatic part still matches the slab


def test_slabs_are_hidden_when_shopify_does_not_apply_what_they_predict(monkeypatch, caplog):
    from app.core.config import settings
    monkeypatch.setattr(settings, "store_discount_slabs", "2500:500:YWPL500,3500:1200:YWPL1200")  # stale setting
    q = shopify_cart.describe(SHOPIFY_CART)
    assert q["slabs"] == {"verified": False}  # nothing about slabs is shown; Shopify's own discount still is
    assert q["discounts"][0]["title"] == "YWPL1000" and "don't match" in caplog.text
    monkeypatch.setattr(settings, "store_discount_slabs", "")
    assert shopify_cart.describe(SHOPIFY_CART)["slabs"] is None
    monkeypatch.setattr(settings, "store_discount_slabs", "2500:abc:YWPL500")
    assert shopify_cart.configured_slabs() == []


def test_below_the_first_slab_no_discount_and_the_next_slab_is_named(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "store_discount_slabs", SLABS)
    cart = {**SHOPIFY_CART, "discountAllocations": [], "lines": {"nodes": [_line("rice-facial-deep-cleansing-foam", 1, 855, 950)]},
            "cost": {"subtotalAmount": {"amount": "855.0", "currencyCode": "INR"}, "totalAmount": {"amount": "855.0", "currencyCode": "INR"}}}
    q = shopify_cart.describe(cart)
    assert q["discounts"] == [] and q["total"] == 855.0
    assert q["slabs"]["verified"] is True and q["slabs"]["current"] is None
    assert q["slabs"]["next"]["title"] == "YWPL500" and q["slabs"]["add_for_next"] == 1645.0


def test_the_cart_endpoint_returns_the_typed_breakdown_and_verified_slab(monkeypatch, catalogue):
    from app.core.config import settings
    monkeypatch.setattr(settings, "store_discount_slabs", SLABS)
    monkeypatch.setattr(shopify_cart, "quote", lambda lines: shopify_cart.describe(SHOPIFY_CART))
    variants = [p.variant_id for p in catalogue.products if p.handle in BASKET]
    r = TestClient(app).post("/v1/shopify/cart", json={"lines": [{"variant_id": v, "quantity": 1} for v in variants]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["subtotal"], body["total"]) == (4995.0, 3995.0)
    assert body["discounts"] == [{"title": "YWPL1000", "amount": 1000.0, "kind": "automatic"}]
    assert body["slabs"]["verified"] and body["slabs"]["add_for_next"] == 505.0
