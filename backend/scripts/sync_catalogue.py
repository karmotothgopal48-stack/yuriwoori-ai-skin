"""
Pulls the REAL, live YuriWoori catalogue from yuriwoori.com's public Shopify
JSON feed and upserts it into the local `products` table. This never invents
product names, prices, or descriptions — everything here comes straight from
the live store, matching the architecture doc's "cached locally" design.

Run manually for now: python scripts/sync_catalogue.py
(Step 19 will turn this into a proper scheduled/webhook-driven sync.)
"""

import sys
import os
import re
import time

import requests

sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.db.models import Product

STORE_URL = "https://yuriwoori.com"

# Maps Shopify product_type / tags to a routine step. Extend as needed —
# unmatched categories fall back to "unassigned" rather than a guess.
CATEGORY_TO_STEP = {
    "cleanser": "cleanse",
    "toner": "tone",
    "ampoule": "treat",
    "serum": "treat",
    "soothing gel": "treat",
    "moisturising cream": "moisturize",
    "moisturizer": "moisturize",
    "sun block": "protect",
    "sunscreen": "protect",
    "eye patch": "treat",
    "sheet mask": "mask",
    "hand cream": "moisturize",
    "make up remover": "cleanse",
}


def strip_html(html: str | None) -> str | None:
    if not html:
        return None
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def fetch_all_products() -> list[dict]:
    products = []
    page = 1
    while True:
        resp = requests.get(
            f"{STORE_URL}/products.json",
            params={"limit": 250, "page": page},
            headers={"User-Agent": "YuriWoori-Catalogue-Sync/1.0"},
            timeout=15,
        )
        resp.raise_for_status()
        batch = resp.json().get("products", [])
        if not batch:
            break
        products.extend(batch)
        page += 1
        time.sleep(0.5)  # be polite to the storefront
    return products


def sync():
    db = SessionLocal()
    raw_products = fetch_all_products()

    if not raw_products:
        print("No products returned — the store's /products.json feed may be disabled. "
              "Falling back to Storefront API is the next step if this happens.")
        return

    created, updated = 0, 0

    for p in raw_products:
        variant = p["variants"][0] if p.get("variants") else {}
        price = float(variant["price"]) if variant.get("price") else None
        image_url = p["images"][0]["src"] if p.get("images") else None
        category_raw = (p.get("product_type") or "").strip().lower()
        routine_step = CATEGORY_TO_STEP.get(category_raw, "unassigned")

        shopify_id = str(p["id"])
        existing = db.query(Product).filter(Product.shopify_product_id == shopify_id).first()

        values = dict(
            name=p["title"],
            price=price,
            currency="INR",
            image_url=image_url,
            category=p.get("product_type") or "uncategorized",
            routine_step=routine_step,
            description=strip_html(p.get("body_html")),
            product_url=f"{STORE_URL}/products/{p['handle']}",
            active=True,
        )

        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(Product(shopify_product_id=shopify_id, **values))
            created += 1

    db.commit()
    db.close()
    print(f"Sync complete: {created} products created, {updated} updated.")


if __name__ == "__main__":
    sync()