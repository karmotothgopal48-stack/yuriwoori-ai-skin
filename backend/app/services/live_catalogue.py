"""
The YuriWoori product catalogue, read live from the official store (https://yuriwoori.com, a Shopify store).

This is the single source of truth for which products exist and everything the app knows about them.
Recommendations, routines, the shopping agent, the coach, checkout and the product endpoints all choose
from it; the products table in PostgreSQL is only a record of what was served (app/services/product_records.py).

Sources, all on the live store:
1. Shopify's Storefront GraphQL API (app/services/shopify_client.py), `products` query, cursor-paged:
   product id, handle, title, description, tags, image, updated_at and variants (id, price, compare-at
   price, availableForSale). Works without a token.
2. The brand's product copy — Shopify metafields custom.benefits, chips, keybenefit, how_to_use, inci:
   - read in the same Storefront query when a token with `unauthenticated_read_metafields` is configured;
   - otherwise from the product page /products/<handle>, where the store embeds the same metafields as
     JSON in <script id="stape-product-data">.
   A product whose copy can't be read gets has_content=False: no concern tags, never matched to a scan
   (nothing is guessed), and it is logged.

Caching: the feed is re-read every CATALOGUE_CACHE_SECONDS. A product's page copy is re-read when the feed
reports the product changed (updated_at) or after CATALOGUE_CONTENT_CACHE_SECONDS. If a refresh fails, the
last good copy is served for at most CATALOGUE_STALE_GRACE_SECONDS more and is marked stale; after that the
catalogue is unavailable (LiveCatalogueUnavailable -> HTTP 503). Nothing falls back to the CSV export.
"""

import html
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.services import shopify_client
from app.services.catalogue_rules import (
    derive_category_and_step,
    derive_concern_tags,
    is_bundle,
    parse_ingredient_list,
    strip_html,
)

logger = logging.getLogger(__name__)

MAX_PAGES = 40  # guard against a product list that never ends
PAGE_WORKERS = 4  # product pages read in parallel over one shared connection pool
REQUEST_RETRIES = 2  # extra attempts per store request after a timeout, network error, 429 or 5xx
RETRY_AFTER_FAILURE_SECONDS = 30  # after a failed (or partly failed) refresh, try the store again this soon
USER_AGENT = "YuriWoori-AI-Skin-Analysis/1.0"
CONTENT_FIELDS = ("benefits", "chips", "keybenefit", "how_to_use", "inci")
_PRODUCT_DATA = re.compile(r'<script[^>]*\bid="stape-product-data"[^>]*>(.*?)</script>', re.S)


class LiveCatalogueUnavailable(RuntimeError):
    """The live store could not be read and there is no recent enough copy to use."""


def store_url() -> str:
    return settings.yuriwoori_store_url.rstrip("/")


def _client() -> httpx.Client:
    return httpx.Client(timeout=settings.catalogue_timeout_seconds, headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                        limits=httpx.Limits(max_connections=PAGE_WORKERS, max_keepalive_connections=PAGE_WORKERS))


_RETRY_STATUS = {429, 500, 502, 503, 504}


def _get(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    """GET with a few retries (short backoff) for timeouts, network errors, rate limiting and server errors."""
    for attempt in range(REQUEST_RETRIES + 1):
        last = attempt == REQUEST_RETRIES
        try:
            r = client.get(url, **kwargs)
        except (httpx.TimeoutException, httpx.NetworkError):
            if last:
                raise
        else:
            if r.status_code not in _RETRY_STATUS or last:
                r.raise_for_status()
                return r
        time.sleep(0.5 * 2 ** attempt)
    raise AssertionError("unreachable")


# ---------- reading the store ----------


_PRODUCT_NODE = """
  id handle title descriptionHtml tags productType updatedAt
  featuredImage { url }
  variants(first: 100) { nodes { id title availableForSale price { amount } compareAtPrice { amount } } }
"""
_METAFIELDS = "metafields(identifiers: [" + ", ".join(f'{{namespace: "custom", key: "{k}"}}' for k in CONTENT_FIELDS) + "]) { key value }"
PRODUCTS_PAGE_SIZE = 100


def _products_query(with_metafields: bool) -> str:
    fields = _PRODUCT_NODE + (_METAFIELDS if with_metafields else "")
    return ("query products($first: Int!, $after: String) { products(first: $first, after: $after) "
            "{ pageInfo { hasNextPage endCursor } nodes {" + fields + "} } }")


def from_storefront(node: dict, with_metafields: bool) -> dict:
    """One Storefront API product node -> the store product shape normalise() reads. With metafields, the
    brand copy comes along as "metafields" (otherwise it is read from the product page)."""
    image = node.get("featuredImage") or {}
    raw = {
        "id": shopify_client.gid_number(node.get("id")),
        "handle": node.get("handle"),
        "title": node.get("title"),
        "body_html": node.get("descriptionHtml"),
        "tags": node.get("tags") or [],
        "product_type": node.get("productType"),
        "updated_at": node.get("updatedAt"),
        "images": [{"src": image["url"]}] if image.get("url") else [],
        "variants": [
            {
                "id": shopify_client.gid_number(v.get("id")),
                "title": v.get("title"),
                "price": (v.get("price") or {}).get("amount"),
                "compare_at_price": (v.get("compareAtPrice") or {}).get("amount"),
                "available": bool(v.get("availableForSale")),
            }
            for v in ((node.get("variants") or {}).get("nodes") or [])
        ],
    }
    if with_metafields:
        raw["metafields"] = {m["key"]: m["value"] for m in node.get("metafields") or [] if m and isinstance(m.get("value"), str)}
    return raw


def _read_products(with_metafields: bool) -> list[dict]:
    products, after = [], None
    with shopify_client._client() as client:
        for _ in range(MAX_PAGES):
            data = shopify_client.storefront(_products_query(with_metafields), {"first": PRODUCTS_PAGE_SIZE, "after": after}, client)
            page = data.get("products") or {}
            nodes = page.get("nodes")
            if not isinstance(nodes, list):
                raise ValueError("the Storefront API returned no product list")
            products.extend(from_storefront(n, with_metafields) for n in nodes)
            info = page.get("pageInfo") or {}
            if not info.get("hasNextPage"):
                return products
            after = info.get("endCursor")
    raise ValueError(f"the Storefront product list did not end within {MAX_PAGES} pages")


def _fetch_raw_products() -> list[dict]:
    """Every product of the store, via the Storefront API (all pages). Metafields are included when the
    configured token allows it; a token without the metafield scope falls back to page copy (logged)."""
    if shopify_client.has_token():
        try:
            return _read_products(with_metafields=True)
        except shopify_client.ShopifyError as exc:
            if "ACCESS_DENIED" not in exc.codes:
                raise
            logger.error("The Storefront token can't read metafields (needs unauthenticated_read_metafields, and the "
                         "custom.* metafields exposed to the storefront); reading product copy from product pages instead")
    return _read_products(with_metafields=False)


def parse_product_page(page_html: str) -> dict | None:
    """The brand's product copy from a product page, or None when the page has no product data block."""
    match = _PRODUCT_DATA.search(page_html)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    custom = ((data.get("metafields") or {}).get("custom") or {}) if isinstance(data, dict) else {}
    return {k: custom[k] for k in CONTENT_FIELDS if isinstance(custom.get(k), str)}


def _fetch_product_content(handle: str, client: httpx.Client) -> dict | None:
    """Product copy from the live product page. None = the page carries no copy; raises on HTTP errors."""
    return parse_product_page(_get(client, f"{store_url()}/products/{handle}").text)


# ---------- normalised products ----------


def _money(value) -> float | None:
    try:
        return round(float(value), 2) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


# How often a product is meant to be used, read ONLY from official YuriWoori text: the product's "How to use"
# copy first, then its live description. The exact sentence is returned with it. Nothing is inferred: if
# neither text states a frequency, frequency is None.
_SENTENCE = re.compile(r"[^.!?]+[.!?]?")
USAGE_PATTERNS = [  # checked in this order within a text; the first match wins
    ("morning_and_night", re.compile(r"\b(morning and (night|evening)|day and night|AM and PM)\b", re.I)),
    ("morning", re.compile(r"\b(morning (routine|skin)|daily morning)\b", re.I)),
    ("daily", re.compile(r"\b(daily|every day)\b", re.I)),
    ("weekly", re.compile(r"\b(weekly|(once|twice|\d+(\s*(-|–|to)\s*\d+)?)\s*(times?\s*)?(a|per)\s*week)\b", re.I)),
    ("as_needed", re.compile(r"\b(as needed|whenever|anytime)\b", re.I)),
]
_WEAR_TIME = re.compile(r"(\d+(?:\s*(?:-|–|to)\s*\d+)?)\s*minutes", re.I)


def _plain(text: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    text = re.sub(r"(?<=\d)\s*�\s*(?=\d)", "–", text)  # a lost en dash between numbers ("15�20")
    return re.sub(r"\s+", " ", text).strip()


def usage_guidance(how_to_use: str | None, description: str | None) -> dict | None:
    """{frequency, quote, source, wear_time} from official text, or None when nothing is stated."""
    how, desc = _plain(how_to_use), _plain(description)
    wear = _WEAR_TIME.search(how)
    found = None
    for source, text in (("how_to_use", how), ("description", desc)):
        sentences = [s.strip() for s in _SENTENCE.findall(text) if s.strip()]
        for frequency, pattern in USAGE_PATTERNS:
            quote = next((s for s in sentences if pattern.search(s)), None)
            if quote:
                found = {"frequency": frequency, "quote": quote, "source": source}
                break
        if found:
            break
    if not found and not wear:
        return None
    return {**(found or {"frequency": None, "quote": None, "source": None}),
            "wear_time": f"{wear.group(1)} minutes" if wear else None}


@dataclass(frozen=True)
class StoreProduct:
    """One product as the official store currently sells it."""
    product_id: int
    handle: str
    name: str
    image_url: str | None
    product_url: str
    description: str | None
    body_html: str | None
    category: str
    routine_step: str
    variant_id: int | None  # the variant a cart line uses: the first available one
    price: float | None
    compare_at_price: float | None  # original price, only when higher than the current price
    discount_percent: int | None
    available: bool
    variants: tuple[dict, ...]
    updated_at: str | None
    has_content: bool  # the product page's brand copy was read
    concern_tags: tuple[str, ...] = ()
    chips: tuple[str, ...] = ()
    benefits_raw: str | None = None
    ingredients: tuple[str, ...] = ()
    key_benefit: str | None = None
    how_to_use: str | None = None
    currency: str = "INR"

    @property
    def variant_gid(self) -> str | None:
        """The Storefront API id of variant_id (cart lines for the Storefront cart API)."""
        return f"gid://shopify/ProductVariant/{self.variant_id}" if self.variant_id else None

    def live_fields(self) -> dict:
        """The LiveProduct response (schemas.LiveProduct)."""
        return {
            "product_id": self.product_id, "handle": self.handle, "title": self.name, "image_url": self.image_url,
            "url": self.product_url, "variant_id": self.variant_id, "price": self.price,
            "compare_at_price": self.compare_at_price, "discount_percent": self.discount_percent,
            "available": self.available, "variants": list(self.variants),
            "usage": usage_guidance(self.how_to_use, self.body_html),
        }


def _tag_text(tags) -> str:
    if isinstance(tags, str):
        return tags
    return ", ".join(t for t in (tags or []) if isinstance(t, str))


def normalise(raw: dict, content: dict | None) -> StoreProduct:
    """One store feed product (+ its page copy, if read) -> StoreProduct. Raises KeyError/TypeError when malformed."""
    handle = raw["handle"]
    title = raw.get("title") or handle
    variants = tuple(
        {
            "id": int(v["id"]),
            "title": v.get("title"),
            "price": _money(v.get("price")),
            "compare_at_price": _money(v.get("compare_at_price")),
            "available": bool(v.get("available")),
        }
        for v in raw.get("variants") or []
    )
    chosen = next((v for v in variants if v["available"]), variants[0] if variants else None)
    price = chosen["price"] if chosen else None
    compare = chosen["compare_at_price"] if chosen else None
    on_sale = price is not None and compare is not None and compare > price
    images = raw.get("images") or []
    tags = _tag_text(raw.get("tags"))
    category, routine_step = derive_category_and_step(tags, handle, title)
    if is_bundle(handle, tags, price):
        category, routine_step = "bundle", "bundle"

    copy = content or {}
    chips, benefits, keybenefit = copy.get("chips", ""), copy.get("benefits", ""), copy.get("keybenefit", "")
    return StoreProduct(
        product_id=int(raw["id"]),
        handle=handle,
        name=title,
        image_url=images[0].get("src") if images else None,
        product_url=f"{store_url()}/products/{handle}",
        description=strip_html(raw.get("body_html")) or strip_html(keybenefit),
        body_html=raw.get("body_html"),
        category=category,
        routine_step=routine_step,
        variant_id=chosen["id"] if chosen else None,
        price=price,
        compare_at_price=compare if on_sale else None,
        discount_percent=round((compare - price) / compare * 100) if on_sale else None,
        available=any(v["available"] for v in variants),
        variants=variants,
        updated_at=raw.get("updated_at"),
        has_content=content is not None,
        # concern tags only from the brand's product copy: without it, nothing is guessed
        concern_tags=tuple(derive_concern_tags(title, chips, benefits, keybenefit)) if content is not None else (),
        chips=tuple(c.strip() for c in chips.split(",") if c.strip()),
        benefits_raw=benefits or None,
        ingredients=tuple(parse_ingredient_list(copy.get("inci"))),
        key_benefit=strip_html(keybenefit),
        how_to_use=strip_html(copy.get("how_to_use")),
    )


@dataclass(frozen=True)
class Catalogue:
    """The store's products at one moment. `stale` = a refresh failed and this is the last good copy."""
    products: tuple[StoreProduct, ...]
    fetched_at: str
    stale: bool = False
    unread_pages: tuple[str, ...] = ()  # products whose page copy could not be read this time (not matched)
    by_handle: dict = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "by_handle", {p.handle: p for p in self.products})

    def get(self, handle: str | None) -> StoreProduct | None:
        return self.by_handle.get(handle) if handle else None


# ---------- refresh and cache ----------

_lock = threading.Lock()
_state: dict = {"catalogue": None, "at": 0.0, "retry_after": 0.0}
_content_cache: dict[str, dict] = {}  # handle -> {"updated_at", "at", "content"}


def _contents_for(raw_products: list[dict]) -> tuple[dict[str, dict | None], list[str]]:
    """(page copy per handle, handles whose page could not be read). Copy is cached while the product is
    unchanged and recent, otherwise re-read."""
    now = time.monotonic()
    result, to_fetch = {}, []
    for raw in raw_products:
        handle, cached = raw["handle"], _content_cache.get(raw["handle"])
        if raw.get("metafields") is not None:  # read with the products via the Storefront API
            result[handle] = {k: v for k, v in raw["metafields"].items() if k in CONTENT_FIELDS} or None
        elif cached and cached["updated_at"] == raw.get("updated_at") and now - cached["at"] < settings.catalogue_content_cache_seconds:
            result[handle] = cached["content"]
        else:
            to_fetch.append(raw)

    failed = []
    if not to_fetch:
        return result, failed
    with _client() as client, ThreadPoolExecutor(max_workers=PAGE_WORKERS) as pool:
        def read(raw):
            try:
                return raw, _fetch_product_content(raw["handle"], client), None
            except (httpx.HTTPError, ValueError) as exc:
                return raw, None, exc

        for raw, content, error in pool.map(read, to_fetch):
            handle, cached = raw["handle"], _content_cache.get(raw["handle"])
            if error is None:
                if content is None:
                    logger.warning("No product copy on the live page of %s: it will not be matched to scans", handle)
                _content_cache[handle] = {"updated_at": raw.get("updated_at"), "at": now, "content": content}
                result[handle] = content
            elif cached and cached["updated_at"] == raw.get("updated_at"):
                # the product itself is unchanged in the store, so its earlier copy is still its copy
                logger.warning("Could not re-read the page of %s (%s); keeping its copy for the unchanged product", handle, error)
                result[handle] = cached["content"]
            else:
                logger.warning("Could not read the page of %s (%s): it will not be matched to scans", handle, error)
                result[handle] = None
                failed.append(handle)
    return result, failed


def _load() -> Catalogue:
    raw_products = [p for p in _fetch_raw_products() if isinstance(p, dict) and p.get("handle") and p.get("id")]
    if not raw_products:
        raise ValueError("the store feed returned no products")
    contents, unread = _contents_for(raw_products)
    products = []
    for raw in raw_products:
        try:
            products.append(normalise(raw, contents.get(raw["handle"])))
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Skipping malformed store product %s: %s", raw.get("handle"), exc)
    return Catalogue(products=tuple(products), fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     unread_pages=tuple(unread))


def get_catalogue() -> Catalogue:
    """The live catalogue (cached). Raises LiveCatalogueUnavailable when the store can't be read and the
    last good copy is older than the cache period plus the stale grace period."""
    with _lock:
        now = time.monotonic()
        current, age = _state["catalogue"], now - _state["at"]
        # a refresh that missed some product pages is retried soon instead of after the full cache period
        fresh_for = RETRY_AFTER_FAILURE_SECONDS if current is not None and current.unread_pages else settings.catalogue_cache_seconds
        if current is not None and age <= fresh_for:
            return current
        usable = current is not None and age <= settings.catalogue_cache_seconds + settings.catalogue_stale_grace_seconds
        if now < _state["retry_after"]:  # the store failed moments ago: don't make every request wait on it
            if usable:
                return replace(current, stale=True)
            raise LiveCatalogueUnavailable(f"Could not load live products from {store_url()}. Please try again shortly.")
        try:
            fresh = _load()
        except (httpx.HTTPError, shopify_client.ShopifyError, ValueError, KeyError, TypeError) as exc:
            _state["retry_after"] = now + RETRY_AFTER_FAILURE_SECONDS
            if usable:
                logger.warning("Live catalogue refresh failed (%s); serving the copy from %s, marked stale", exc, current.fetched_at)
                return replace(current, stale=True)
            logger.error("Live catalogue unavailable: %s", exc)
            raise LiveCatalogueUnavailable(f"Could not load live products from {store_url()}. Please try again shortly.") from exc
        _state.update(catalogue=fresh, at=now, retry_after=0.0)
        return fresh


def clear_cache() -> None:
    with _lock:
        _state.update(catalogue=None, at=0.0, retry_after=0.0)
        _content_cache.clear()
