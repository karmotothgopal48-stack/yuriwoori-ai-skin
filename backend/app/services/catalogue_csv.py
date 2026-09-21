"""
Reads the YuriWoori catalogue straight from data/products_export.csv (the Shopify
product export) and recommends products for a skin analysis - no database needed.

Nothing here is invented: names, prices, images and ingredient lists come from the
CSV, and concern tags are derived by keyword-matching the brand's own copy (see
CONCERN_KEYWORDS). The parsing helpers are shared with scripts/import_catalogue_csv.py.
"""

import csv
import os
import re
from dataclasses import dataclass, field

CSV_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "products_export.csv")
)

TAG_TO_STEP = {
    "cleanser": "cleanse",
    "toner": "tone",
    "serum": "treat",
    "soothing-gel": "treat",
    "moisturizer": "moisturize",
    "sunscreen": "protect",
    "facemask": "mask",
    "handcream": "moisturize",
}

# Keyword -> concern tag, scanned across title/benefits/chips text.
# This CATEGORIZES the brand's own real marketing copy — it never invents claims.
CONCERN_KEYWORDS = {
    "hydrat": "hydration",
    "moistur": "hydration",
    "bright": "brightening",
    "even": "uneven-tone",
    "sooth": "soothing",
    "calm": "soothing",
    "anti-aging": "anti-aging",
    "firm": "anti-aging",
    "pore": "pore-visibility",
    "oil-control": "oiliness",
    "oil control": "oiliness",
    "acne": "blemish",
    "blemish": "blemish",
    "barrier": "barrier-repair",
    "redness": "redness",
    "sun": "sun-protection",
}


def strip_html(html: str | None) -> str | None:
    if not html:
        return None
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


# Some real products carry only the generic "enhance-kit" tag, so the step is
# read from the product's own name/handle instead. Order matters (first hit wins).
NAME_TO_STEP = [
    (("make-up-remover", "makeup-remover", "make up remover"), "cleanse"),
    (("cleansing", "cleanser"), "cleanse"),
    (("sun-gel", "sunscreen", "sun-block", "sun block", "sun-cream"), "protect"),
    (("eye-patch", "eye patch"), "treat"),
    (("mask-sheet", "sheet-mask", "sheet mask", "hyaluronic-acid-sheet"), "mask"),
    (("hand-cream",), "moisturize"),
]

BUNDLE_WORDS = ("-kit", "-duo", "-trio", "-combo", "bundle")


def is_bundle(handle: str, tags: str, price: float | None) -> bool:
    """Kits/combos are multi-product sets, not single routine steps."""
    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    if "byobsuite" in tag_list or (price is not None and price <= 0):
        return True
    return not tag_list and any(w in handle.lower() for w in BUNDLE_WORDS)


def derive_category_and_step(tags: str, handle: str = "", title: str = "") -> tuple[str, str]:
    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    for tag in tag_list:
        if tag in TAG_TO_STEP:
            return tag, TAG_TO_STEP[tag]
    haystack = f"{handle} {title}".lower()
    for keywords, step in NAME_TO_STEP:
        if any(k in haystack for k in keywords):
            return (tag_list[0] if tag_list else "uncategorized"), step
    return (tag_list[0] if tag_list else "uncategorized"), "unassigned"


def derive_concern_tags(*texts: str) -> list[str]:
    blob = " ".join(t.lower() for t in texts if t)
    found = set()
    for keyword, tag in CONCERN_KEYWORDS.items():
        # Match at a word start so stems like "hydrat" still work but "even"
        # does not fire inside "seven" / "prevent".
        if re.search("(?<![a-z])" + re.escape(keyword), blob):
            found.add(tag)
    return sorted(found)


def parse_ingredient_list(inci_text: str) -> list[str]:
    if not inci_text:
        return []
    # INCI lists are comma-separated; strip stray whitespace/newlines.
    raw = [i.strip() for i in inci_text.replace("\n", ",").split(",")]
    return [i for i in raw if i and len(i) > 1]


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


def _row_to_product(row: dict) -> CsvProduct:
    handle, title = row["Handle"], row["Title"]
    price_raw = (row.get("Variant Price") or "").strip()
    price = float(price_raw) if price_raw else None
    tags = row.get("Tags", "")
    chips = row.get("chips (product.metafields.custom.chips)", "")
    benefits = row.get("benefits (product.metafields.custom.benefits)", "")
    keybenefit = row.get("keybenefit (product.metafields.custom.keybenefit)", "")
    inci = row.get("inci (product.metafields.custom.inci)", "")

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


# ---------- recommendations ----------


def concern_details(metrics: dict) -> dict[str, tuple[str, float]]:
    """Skin metrics -> {concern tag: (human phrase, severity 0-1)} for every concern above its
    threshold. Severity is how far past the threshold the metric is, so a worse scan ranks higher.
    Uses the same rules as the database recommender (services/recommendation.py)."""
    from app.services.recommendation import CONCERN_RULES

    found: dict[str, tuple[str, float]] = {}
    for attr, threshold, tag, phrase in CONCERN_RULES:
        value = metrics.get(attr)
        if value is not None and value > threshold:
            found[tag] = (phrase, (value - threshold) / (100 - threshold))

    hydration = metrics.get("hydration")
    if hydration is not None and hydration < 45:
        found["hydration"] = ("boost hydration", (45 - hydration) / 45)
    return found


def active_concerns(metrics: dict) -> dict[str, str]:
    """{concern tag: human phrase} for every concern the analysis flagged."""
    return {tag: phrase for tag, (phrase, _) in concern_details(metrics).items()}


def recommend(metrics: dict, limit_per_step: int = 2) -> tuple[dict[str, str], list[dict]]:
    """Returns (active concerns, ranked recommendations). A product is only recommended
    if its own concern tags overlap a real concern from the scan."""
    details = concern_details(metrics)
    concerns = {tag: phrase for tag, (phrase, _) in details.items()}
    if not concerns:
        return concerns, []

    scored = []
    for p in load_catalogue():
        if p.routine_step == "bundle" or not p.price:
            continue  # kits/combos and unpriced entries are not single routine products
        overlap = sorted(set(p.concern_tags) & concerns.keys())
        if not overlap:
            continue
        reasons = [concerns[t] for t in overlap]
        scored.append({
            "product": p,
            # each matched concern is worth 10, plus up to 10 more the worse that concern is in the scan
            "score": round(sum(10 + 10 * details[t][1] for t in overlap)),
            "matched_concerns": overlap,
            "match_reason": f"Matches your scan: helps {', '.join(dict.fromkeys(reasons))}.",
        })

    scored.sort(key=lambda x: (-x["score"], x["product"].name))

    per_step: dict[str, int] = {}
    final = []
    for item in scored:
        step = item["product"].routine_step or "unassigned"
        per_step[step] = per_step.get(step, 0) + 1
        if per_step[step] <= limit_per_step:
            final.append(item)
    return concerns, final
