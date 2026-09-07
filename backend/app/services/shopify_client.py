"""
Thin wrapper over Shopify's real Storefront GraphQL API. Every call here
hits your live store — no mocked responses.
"""

import requests
from app.core.config import settings

API_VERSION = "2024-10"


def _endpoint() -> str:
    return f"https://{settings.shopify_store_domain}/api/{API_VERSION}/graphql.json"


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "X-Shopify-Storefront-Access-Token": settings.shopify_storefront_access_token,
    }


def _post(query: str, variables: dict) -> dict:
    resp = requests.post(_endpoint(), json={"query": query, "variables": variables}, headers=_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"Shopify Storefront API error: {data['errors']}")
    return data["data"]


def get_variant_id_by_handle(handle: str) -> str | None:
    query = """
    query getVariant($handle: String!) {
      productByHandle(handle: $handle) {
        variants(first: 1) {
          edges { node { id } }
        }
      }
    }
    """
    data = _post(query, {"handle": handle})
    product = data.get("productByHandle")
    if not product or not product["variants"]["edges"]:
        return None
    return product["variants"]["edges"][0]["node"]["id"]


def create_cart(lines: list[dict]) -> dict:
    """lines: [{"merchandiseId": "gid://shopify/ProductVariant/...", "quantity": 1}, ...]"""
    query = """
    mutation cartCreate($lines: [CartLineInput!]) {
      cartCreate(input: { lines: $lines }) {
        cart {
          id
          checkoutUrl
        }
        userErrors { field message }
      }
    }
    """
    data = _post(query, {"lines": lines})
    result = data["cartCreate"]
    if result["userErrors"]:
        raise RuntimeError(f"Shopify cart creation error: {result['userErrors']}")
    return result["cart"]