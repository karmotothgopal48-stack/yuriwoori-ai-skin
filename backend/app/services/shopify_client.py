"""
Client for Shopify's Storefront GraphQL API of the official YuriWoori store — the supported API for reading
products and building carts. Every call goes to the live store; nothing is mocked.

    POST https://<store>/api/<SHOPIFY_API_VERSION>/graphql.json
    Content-Type: application/json
    body: {"query": "<GraphQL>", "variables": {...}}

Products, prices, availability and carts work WITHOUT a token (Shopify "tokenless" Storefront access; verified
for this store). Reading custom metafields (benefits, INCI, how to use) needs a token with the
`unauthenticated_read_metafields` scope: set SHOPIFY_STOREFRONT_PRIVATE_TOKEN (server-side, preferred) or
SHOPIFY_STOREFRONT_ACCESS_TOKEN. Tokens stay on the server; they are never sent to the browser.
"""

import time

import httpx

from app.core.config import settings

REQUEST_RETRIES = 2  # extra attempts after a timeout, network error, 429 or 5xx
_RETRY_STATUS = {429, 500, 502, 503, 504}


class ShopifyError(RuntimeError):
    """Shopify answered with GraphQL errors (e.g. ACCESS_DENIED) or an unusable response."""

    def __init__(self, message: str, codes: tuple[str, ...] = ()):
        super().__init__(message)
        self.codes = codes


def endpoint() -> str:
    base = f"https://{settings.shopify_store_domain}" if settings.shopify_store_domain else settings.yuriwoori_store_url.rstrip("/")
    return f"{base}/api/{settings.shopify_api_version}/graphql.json"


def has_token() -> bool:
    return bool(settings.shopify_storefront_private_token or settings.shopify_storefront_access_token)


def _headers() -> dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "YuriWoori-AI-Skin-Analysis/1.0"}
    if settings.shopify_storefront_private_token:
        headers["Shopify-Storefront-Private-Token"] = settings.shopify_storefront_private_token
    elif settings.shopify_storefront_access_token:
        headers["X-Shopify-Storefront-Access-Token"] = settings.shopify_storefront_access_token
    return headers


def _client() -> httpx.Client:
    return httpx.Client(timeout=settings.catalogue_timeout_seconds, follow_redirects=True)


def storefront(query: str, variables: dict | None = None, client: httpx.Client | None = None) -> dict:
    """The `data` of one Storefront GraphQL request. Raises httpx.HTTPError for transport/HTTP failures
    and ShopifyError for GraphQL errors."""
    own = client is None
    client = client or _client()
    try:
        for attempt in range(REQUEST_RETRIES + 1):
            last = attempt == REQUEST_RETRIES
            try:
                r = client.post(endpoint(), json={"query": query, "variables": variables or {}}, headers=_headers())
            except (httpx.TimeoutException, httpx.NetworkError):
                if last:
                    raise
            else:
                if r.status_code not in _RETRY_STATUS or last:
                    r.raise_for_status()
                    break
            time.sleep(0.5 * 2 ** attempt)
    finally:
        if own:
            client.close()
    body = r.json()
    if body.get("errors"):
        errors = body["errors"]
        codes = tuple(str((e.get("extensions") or {}).get("code")) for e in errors if isinstance(e, dict))
        raise ShopifyError("Shopify Storefront API error: " + "; ".join(str(e.get("message")) for e in errors if isinstance(e, dict)), codes)
    if not isinstance(body.get("data"), dict):
        raise ShopifyError("Shopify Storefront API returned no data")
    return body["data"]


def gid_number(gid: str | int | None) -> int | None:
    """gid://shopify/ProductVariant/44562254495778 -> 44562254495778."""
    if gid is None:
        return None
    try:
        return int(str(gid).rsplit("/", 1)[-1])
    except ValueError:
        return None


def variant_gid(variant_id: int) -> str:
    return f"gid://shopify/ProductVariant/{int(variant_id)}"


def get_variant_id_by_handle(handle: str) -> str | None:
    """First variant GID of a product (used by the legacy scripts/resolve_shopify_variants.py)."""
    data = storefront("query($h: String!) { product(handle: $h) { variants(first: 1) { nodes { id } } } }", {"h": handle})
    nodes = ((data.get("product") or {}).get("variants") or {}).get("nodes") or []
    return nodes[0]["id"] if nodes else None


# ---------- cart ----------

_CART_FIELDS = """
  id checkoutUrl totalQuantity
  cost { subtotalAmount { amount currencyCode } totalAmount { amount currencyCode } }
  discountCodes { code applicable }
  discountAllocations {
    __typename
    discountedAmount { amount }
    ... on CartAutomaticDiscountAllocation { title }
    ... on CartCodeDiscountAllocation { code }
    ... on CartCustomDiscountAllocation { title }
  }
  lines(first: 100) { nodes {
    id quantity
    merchandise { ... on ProductVariant { id title product { handle title } image { url } } }
    cost { amountPerQuantity { amount } compareAtAmountPerQuantity { amount } subtotalAmount { amount } totalAmount { amount } }
    discountAllocations {
      __typename
      discountedAmount { amount }
      ... on CartAutomaticDiscountAllocation { title }
      ... on CartCodeDiscountAllocation { code }
      ... on CartCustomDiscountAllocation { title }
    }
  } }
"""

CART_CREATE = "mutation cartCreate($input: CartInput!) { cartCreate(input: $input) { cart {" + _CART_FIELDS + "} userErrors { field message } warnings { code message } } }"


def create_cart(lines: list[dict]) -> dict:
    """Create a Shopify cart. lines: [{"merchandiseId": "gid://shopify/ProductVariant/...", "quantity": 1}, ...].
    Returns the cart (with Shopify's own cost and discounts). Raises ShopifyError on userErrors."""
    result = storefront(CART_CREATE, {"input": {"lines": lines}})["cartCreate"]
    if result.get("userErrors"):
        raise ShopifyError("Shopify cart error: " + "; ".join(e.get("message", "") for e in result["userErrors"]))
    if not result.get("cart"):
        raise ShopifyError("Shopify did not return a cart")
    cart = result["cart"]
    cart["warnings"] = result.get("warnings") or []
    return cart
