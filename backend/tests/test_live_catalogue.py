"""
The live catalogue service (app/services/live_catalogue.py): reading and normalising the official store,
pagination, retries, page copy, caching, staleness and failures. The store is stubbed: no network.
"""

import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import live_catalogue
from app.services.live_catalogue import LiveCatalogueUnavailable, get_catalogue
from app.services.recommendation import is_selectable, recommend

# the real store reader (tests/conftest.py replaces it with the snapshot during each test)
fetch_raw_products = live_catalogue._fetch_raw_products

COPY = {"chips": "Deep hydration", "benefits": "x|Hydrating|Keeps skin moisturised", "keybenefit": "Moisture care.",
        "how_to_use": "Apply morning and night.", "inci": "Water, Glycerin, ​Niacinamide"}

STORE = [
    {"id": 1, "handle": "on-sale", "title": "On Sale Cream", "tags": ["moisturizer"], "updated_at": "t1",
     "images": [{"src": "https://cdn.example/a.webp"}],
     "variants": [{"id": 11, "title": "Default", "price": "855.00", "compare_at_price": "950.00", "available": True}]},
    {"id": 2, "handle": "full-price", "title": "Full Price Toner", "tags": ["toner"], "images": [],
     "variants": [{"id": 21, "title": "Default", "price": "500.00", "compare_at_price": None, "available": True}]},
    {"id": 3, "handle": "sold-out", "title": "Sold Out Gel", "tags": ["serum"], "images": [{"src": "https://cdn.example/c.webp"}],
     "variants": [{"id": 31, "title": "Default", "price": "300.00", "compare_at_price": "300.00", "available": False}]},
    {"id": 4, "handle": "no-variants", "title": "Ghost Serum", "tags": ["serum"], "images": [], "variants": []},
    {"id": 5, "handle": "second-variant", "title": "Two Sizes Cream", "tags": ["moisturizer"], "images": [],
     "variants": [{"id": 51, "title": "50ml", "price": "900.00", "available": False},
                  {"id": 52, "title": "30ml", "price": "600.00", "available": True}]},
    {"handle": "no-id", "title": "Broken"},  # malformed: skipped
]


@pytest.fixture
def store(monkeypatch):
    """A small stub store; every product has page copy unless a test changes `pages`."""
    pages = {p["handle"]: COPY for p in STORE}
    calls = {"feed": 0, "pages": []}

    def feed():
        calls["feed"] += 1
        return STORE

    def page(handle, client):
        calls["pages"].append(handle)
        value = pages.get(handle)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(live_catalogue, "_fetch_raw_products", feed)
    monkeypatch.setattr(live_catalogue, "_fetch_product_content", page)
    monkeypatch.setattr(live_catalogue.time, "sleep", lambda s: None)
    live_catalogue.clear_cache()
    return {"pages": pages, "calls": calls}


def _down(*_args, **_kwargs):
    raise httpx.ConnectError("store down")


def _expire(extra=0):
    live_catalogue._state["at"] = time.monotonic() - settings.catalogue_cache_seconds - 1 - extra
    live_catalogue._state["retry_after"] = 0.0


# ---------- normalising ----------


def test_prices_discounts_and_variants_come_from_the_store(store):
    c = get_catalogue()
    assert c.fetched_at and not c.stale
    on_sale, full, sold_out = c.get("on-sale"), c.get("full-price"), c.get("sold-out")
    assert (on_sale.price, on_sale.compare_at_price, on_sale.discount_percent) == (855.0, 950.0, 10)
    assert on_sale.variant_id == 11 and on_sale.variant_gid == "gid://shopify/ProductVariant/11"
    assert on_sale.product_url.endswith("/products/on-sale") and on_sale.product_id == 1
    assert full.compare_at_price is None and full.discount_percent is None
    assert sold_out.available is False and sold_out.compare_at_price is None  # equal price is not a discount


def test_cart_variant_is_the_first_available_one(store):
    p = get_catalogue().get("second-variant")
    assert p.variant_id == 52 and p.price == 600.0 and p.available


def test_unbuyable_products_are_listed_but_never_selected(store):
    c = get_catalogue()
    ghost = c.get("no-variants")
    assert ghost.variant_id is None and ghost.price is None and ghost.available is False
    assert not is_selectable(ghost) and not is_selectable(c.get("sold-out"))
    assert is_selectable(c.get("on-sale"))
    _, ranked = recommend({"hydration": 10}, c.products)
    handles = {r["product"].handle for r in ranked}
    assert "on-sale" in handles and not handles & {"no-variants", "sold-out"}


def test_malformed_store_products_are_skipped(store):
    assert get_catalogue().get("no-id") is None and len(get_catalogue().products) == 5


def test_page_copy_drives_step_tags_and_ingredients(store):
    p = get_catalogue().get("on-sale")
    assert p.has_content and p.routine_step == "moisturize" and p.category == "moisturizer"
    assert "hydration" in p.concern_tags
    assert p.ingredients == ("Water", "Glycerin", "Niacinamide")  # invisible characters removed
    assert p.how_to_use == "Apply morning and night." and p.key_benefit == "Moisture care."


def test_a_product_without_page_copy_is_never_matched(store):
    store["pages"]["on-sale"] = None  # the page has no product data block
    p = get_catalogue().get("on-sale")
    assert not p.has_content and p.concern_tags == ()
    matched = {r["product"].handle for r in recommend({"hydration": 10}, get_catalogue().products)[1]}
    assert "on-sale" not in matched and "second-variant" in matched  # same copy, but read from its page


# ---------- reading the store ----------


def test_product_page_copy_is_read_from_the_embedded_product_json():
    data = {"id": 1, "metafields": {"custom": {**COPY, "ribbon": "x", "count": 3}}}
    page = f'<html><script type="application/json" id="stape-product-data">{json.dumps(data)}</script></html>'
    assert live_catalogue.parse_product_page(page) == COPY  # only the copy fields, only strings
    assert live_catalogue.parse_product_page("<html>no block</html>") is None
    assert live_catalogue.parse_product_page('<script id="stape-product-data">{broken</script>') is None


def _mock_client(monkeypatch, handler):
    """Storefront API requests answered by `handler` (shopify_client's HTTP client), no network."""
    from app.services import shopify_client
    monkeypatch.setattr(shopify_client, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(shopify_client.time, "sleep", lambda s: None)


def _node(i, **extra):
    return {"id": f"gid://shopify/Product/{i}", "handle": f"p{i}", "title": f"Product {i}", "descriptionHtml": "<p>Hydrating.</p>",
            "tags": ["toner"], "updatedAt": "2026-10-01T00:00:00Z", "featuredImage": {"url": f"https://cdn.example/{i}.webp"},
            "variants": {"nodes": [{"id": f"gid://shopify/ProductVariant/{i}0", "title": "Default", "availableForSale": True,
                                    "price": {"amount": "765.0"}, "compareAtPrice": {"amount": "850.0"}}]}, **extra}


def test_products_are_read_from_the_storefront_api_across_all_pages(monkeypatch):
    sent = []

    def handler(request):
        body = json.loads(request.content)
        sent.append((request.method, request.url.path, request.headers.get("content-type"), body["variables"]))
        after = body["variables"]["after"]
        page = {None: (range(0, 100), "c1"), "c1": (range(100, 200), "c2"), "c2": (range(200, 207), None)}[after]
        return httpx.Response(200, json={"data": {"products": {"pageInfo": {"hasNextPage": page[1] is not None, "endCursor": page[1]},
                                                                "nodes": [_node(i) for i in page[0]]}}})

    _mock_client(monkeypatch, handler)
    products = fetch_raw_products()
    assert len(products) == 207 and products[-1]["handle"] == "p206"
    method, path, content_type, variables = sent[0]
    assert (method, path, content_type) == ("POST", f"/api/{settings.shopify_api_version}/graphql.json", "application/json")
    assert variables == {"first": 100, "after": None} and sent[1][3]["after"] == "c1"
    first = products[0]  # Storefront GIDs and money objects become the store product shape
    assert first["id"] == 0 and first["variants"][0] == {"id": 0, "title": "Default", "price": "765.0", "compare_at_price": "850.0", "available": True}
    assert "metafields" not in first  # no token: the copy is read from the product page


def test_with_a_token_the_brand_copy_comes_from_storefront_metafields(monkeypatch):
    seen = {}

    def handler(request):
        seen["headers"], seen["query"] = request.headers, json.loads(request.content)["query"]
        return httpx.Response(200, json={"data": {"products": {"pageInfo": {"hasNextPage": False}, "nodes": [
            _node(1, metafields=[{"key": "chips", "value": "Deep hydration"}, {"key": "inci", "value": "Water, Glycerin"}, None])]}}})

    _mock_client(monkeypatch, handler)
    monkeypatch.setattr(settings, "shopify_storefront_private_token", "server-only-token")
    [raw] = fetch_raw_products()
    assert seen["headers"]["Shopify-Storefront-Private-Token"] == "server-only-token"
    assert 'namespace: "custom", key: "how_to_use"' in seen["query"]
    assert raw["metafields"] == {"chips": "Deep hydration", "inci": "Water, Glycerin"}
    contents, unread = live_catalogue._contents_for([raw])
    assert contents == {"p1": {"chips": "Deep hydration", "inci": "Water, Glycerin"}} and unread == []  # no page read


def test_a_token_without_the_metafield_scope_falls_back_to_page_copy(monkeypatch):
    queries = []

    def handler(request):
        query = json.loads(request.content)["query"]
        queries.append(query)
        if "metafields" in query:
            return httpx.Response(200, json={"errors": [{"message": "Access denied for metafield field.",
                                                         "extensions": {"code": "ACCESS_DENIED"}}]})
        return httpx.Response(200, json={"data": {"products": {"pageInfo": {"hasNextPage": False}, "nodes": [_node(1)]}}})

    _mock_client(monkeypatch, handler)
    monkeypatch.setattr(settings, "shopify_storefront_access_token", "public-token")
    [raw] = fetch_raw_products()
    assert len(queries) == 2 and "metafields" not in raw


def test_storefront_errors_and_missing_data_are_failures(monkeypatch):
    from app.services.shopify_client import ShopifyError
    _mock_client(monkeypatch, lambda request: httpx.Response(200, json={"errors": [{"message": "Throttled", "extensions": {"code": "THROTTLED"}}]}))
    with pytest.raises(ShopifyError):
        fetch_raw_products()
    _mock_client(monkeypatch, lambda request: httpx.Response(200, json={"data": {"products": {"nodes": None}}}))
    with pytest.raises(ValueError):
        fetch_raw_products()


def test_store_requests_are_retried_then_fail_clearly(monkeypatch):
    attempts = []
    empty = {"data": {"products": {"pageInfo": {"hasNextPage": False}, "nodes": []}}}

    def flaky(request):
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.ConnectTimeout("slow")
        if len(attempts) == 2:
            return httpx.Response(503)
        return httpx.Response(200, json=empty)

    from app.services import shopify_client
    _mock_client(monkeypatch, flaky)
    assert fetch_raw_products() == [] and len(attempts) == 3

    attempts.clear()
    _mock_client(monkeypatch, lambda request: (attempts.append(1), httpx.Response(503))[1])
    with pytest.raises(httpx.HTTPStatusError):
        fetch_raw_products()
    assert len(attempts) == shopify_client.REQUEST_RETRIES + 1

    attempts.clear()
    _mock_client(monkeypatch, lambda request: (attempts.append(1), httpx.Response(404))[1])
    with pytest.raises(httpx.HTTPStatusError):
        fetch_raw_products()
    assert len(attempts) == 1  # not retried: a 404 won't change


# ---------- caching, staleness, failures ----------


def test_catalogue_is_cached(store):
    get_catalogue()
    get_catalogue()
    assert store["calls"]["feed"] == 1


def test_unchanged_product_copy_is_reused_and_changed_products_are_re_read(store, monkeypatch):
    get_catalogue()
    assert len(store["calls"]["pages"]) == 5
    store["calls"]["pages"].clear()
    _expire()
    monkeypatch.setitem(STORE[0], "updated_at", "t2")  # the store reports on-sale changed
    get_catalogue()
    assert store["calls"]["pages"] == ["on-sale"]


def test_last_copy_is_served_briefly_and_flagged_stale_when_the_store_fails(store, monkeypatch):
    first = get_catalogue()
    monkeypatch.setattr(live_catalogue, "_fetch_raw_products", _down)
    _expire()
    stale = get_catalogue()
    assert stale.stale and stale.fetched_at == first.fetched_at and stale.get("on-sale").price == 855.0


def test_too_old_a_copy_is_never_served(store, monkeypatch):
    get_catalogue()
    monkeypatch.setattr(live_catalogue, "_fetch_raw_products", _down)
    _expire(extra=settings.catalogue_stale_grace_seconds)
    with pytest.raises(LiveCatalogueUnavailable):
        get_catalogue()


def test_after_a_failure_requests_fail_fast_instead_of_waiting_on_the_store(store, monkeypatch):
    calls = []
    monkeypatch.setattr(live_catalogue, "_fetch_raw_products", lambda: (calls.append(1), _down())[1])
    for _ in range(3):
        with pytest.raises(LiveCatalogueUnavailable):
            get_catalogue()
    assert len(calls) == 1


def test_an_empty_store_feed_is_a_failure_not_an_empty_catalogue(store, monkeypatch):
    monkeypatch.setattr(live_catalogue, "_fetch_raw_products", lambda: [])
    with pytest.raises(LiveCatalogueUnavailable):
        get_catalogue()


def test_unread_pages_are_reported_and_retried_soon(store):
    store["pages"]["on-sale"] = httpx.ReadTimeout("slow page")
    c = get_catalogue()
    assert c.unread_pages == ("on-sale",) and not c.get("on-sale").has_content
    store["pages"]["on-sale"] = COPY
    live_catalogue._state["at"] = time.monotonic() - live_catalogue.RETRY_AFTER_FAILURE_SECONDS - 1  # well within the cache period
    c = get_catalogue()
    assert c.unread_pages == () and c.get("on-sale").has_content


def test_a_failed_page_keeps_its_copy_while_the_product_is_unchanged(store):
    get_catalogue()
    live_catalogue._content_cache["on-sale"]["at"] = 0.0  # copy due for a re-read
    store["pages"]["on-sale"] = httpx.ReadTimeout("slow page")
    _expire()
    p = get_catalogue().get("on-sale")
    assert p.has_content and "hydration" in p.concern_tags


# ---------- API ----------


def test_live_api_returns_products_stale_flag_and_503_without_any_copy(store, monkeypatch):
    client = TestClient(app)
    r = client.get("/v1/catalogue/live", params={"handles": "on-sale,full-price,not-in-store"})
    assert r.status_code == 200
    body = r.json()
    assert [p["handle"] for p in body["products"]] == ["on-sale", "full-price"] and body["stale"] is False
    assert body["products"][0]["variant_id"] == 11 and body["products"][0]["usage"]["frequency"] == "morning_and_night"

    live_catalogue.clear_cache()
    monkeypatch.setattr(live_catalogue, "_fetch_raw_products", _down)
    r = client.get("/v1/catalogue/live", params={"handles": "on-sale"})
    assert r.status_code == 503 and "yuriwoori.com" in r.json()["detail"]
    assert client.get("/v1/catalogue/live", params={"handles": " , "}).status_code == 400


def test_every_product_endpoint_reports_503_when_the_store_is_unavailable(store, monkeypatch):
    monkeypatch.setattr(live_catalogue, "_fetch_raw_products", _down)
    client = TestClient(app)
    assert client.get("/v1/catalogue/products").status_code == 503
    assert client.get("/v1/catalogue/products/on-sale").status_code == 503
    assert client.get("/v1/catalogue/recommendations", params={"hydration": 10}).status_code == 503


# ---------- usage guidance ----------


def test_usage_frequency_is_quoted_from_official_text_only():
    from app.services.live_catalogue import usage_guidance
    # "How to use" copy wins over the description, and the exact sentence is kept
    u = usage_guidance("After toner, apply 2-3 drops. Use morning and night for intense hydration.", "Perfect for daily use.")
    assert u["frequency"] == "morning_and_night" and u["source"] == "how_to_use"
    assert u["quote"] == "Use morning and night for intense hydration."
    # falls back to the live description
    u = usage_guidance("Apply on clean skin and leave for 15�20 minutes.", "<p>Use it <b>weekly</b> for a radiant glow.</p>")
    assert u["frequency"] == "weekly" and u["source"] == "description" and u["wear_time"] == "15–20 minutes"
    # nothing stated -> nothing invented (wear time alone is still reported)
    u = usage_guidance("Apply on clean skin for 15 minutes.", "A soothing sheet mask.")
    assert u["frequency"] is None and u["quote"] is None and u["wear_time"] == "15 minutes"
    assert usage_guidance("Apply after cleansing.", "A gentle toner.") is None


def test_real_store_snapshot_has_page_copy_for_every_product(catalogue):
    assert catalogue.unread_pages == () and all(p.has_content for p in catalogue.products)
    toner = catalogue.get("bubble-soothing-toner")
    assert toner.how_to_use.startswith("After cleansing") and "usage" in toner.live_fields()
