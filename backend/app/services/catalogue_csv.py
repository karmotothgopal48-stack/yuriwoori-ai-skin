"""
Reads the Shopify product export CSV (data/products_export.csv).

LEGACY / OFFLINE ONLY: the app no longer reads this file at runtime. The official store at
https://yuriwoori.com is the product catalogue (app/services/live_catalogue.py). This reader remains for
scripts/import_catalogue_csv.py and as an offline reference; the categorising rules it applies are the same
ones the live catalogue uses (app/services/catalogue_rules.py).
"""

import csv
import os
from dataclasses import dataclass, field

from app.services.catalogue_rules import (  # noqa: F401  (re-exported for scripts/import_catalogue_csv.py)
    BUNDLE_WORDS,
    CONCERN_KEYWORDS,
    NAME_TO_STEP,
    TAG_TO_STEP,
    derive_category_and_step,
    derive_concern_tags,
    is_bundle,
    parse_ingredient_list,
    strip_html,
)

CSV_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "products_export.csv")
)


# ---------- catalogue loading ----------


@dataclass(frozen=True)
class CsvProduct:
    handle: str
    name: str
    price: float | None
    image_url: str | None
    category: str
    routine_step: str
    description: str | None
    product_url: str
    concern_tags: tuple[str, ...] = ()
    chips: tuple[str, ...] = ()
    benefits_raw: str | None = None
    ingredients: tuple[str, ...] = field(default=())
    # Verbatim brand copy from the export's metafields (None when the product has none).
    key_benefit: str | None = None
    how_to_use: str | None = None


def _row_to_product(row: dict) -> CsvProduct:
    handle, title = row["Handle"], row["Title"]
    price_raw = (row.get("Variant Price") or "").strip()
    price = float(price_raw) if price_raw else None
    tags = row.get("Tags", "")
    chips = row.get("chips (product.metafields.custom.chips)", "")
    benefits = row.get("benefits (product.metafields.custom.benefits)", "")
    keybenefit = row.get("keybenefit (product.metafields.custom.keybenefit)", "")
    inci = row.get("inci (product.metafields.custom.inci)", "")
    how_to_use = row.get("How to Use (product.metafields.custom.how_to_use)", "")

    category, routine_step = derive_category_and_step(tags, handle, title)
    if is_bundle(handle, tags, price):
        category, routine_step = "bundle", "bundle"

    return CsvProduct(
        handle=handle,
        name=title,
        price=price,
        image_url=row.get("Image Src") or None,
        category=category,
        routine_step=routine_step,
        description=strip_html(row.get("Body (HTML)")) or keybenefit or None,
        product_url=f"https://yuriwoori.com/products/{handle}",
        concern_tags=tuple(derive_concern_tags(title, chips, benefits, keybenefit)),
        chips=tuple(c.strip() for c in chips.split(",") if c.strip()),
        benefits_raw=benefits or None,
        ingredients=tuple(parse_ingredient_list(inci)),
        key_benefit=strip_html(keybenefit),
        how_to_use=strip_html(how_to_use),
    )


_cache: tuple[float, list[CsvProduct]] | None = None


def load_catalogue() -> list[CsvProduct]:
    """Active, published products from the CSV. Re-read automatically when the file changes."""
    global _cache
    mtime = os.path.getmtime(CSV_PATH)
    if _cache and _cache[0] == mtime:
        return _cache[1]

    products = []
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if not (row.get("Title") or "").strip():
                continue  # image/variant-only rows for an already-seen product
            if (row.get("Status") or "active").strip().lower() != "active":
                continue
            if (row.get("Published") or "true").strip().lower() != "true":
                continue
            products.append(_row_to_product(row))

    _cache = (mtime, products)
    return products


def get_product(handle: str) -> CsvProduct | None:
    return next((p for p in load_catalogue() if p.handle == handle), None)
