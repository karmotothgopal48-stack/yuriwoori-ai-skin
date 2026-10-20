"""
How a YuriWoori product is categorised: its routine step, whether it is a bundle, and the concern tags it
addresses. Applied to the live store catalogue (app/services/live_catalogue.py) and, for the legacy import
script, to the Shopify CSV export (app/services/catalogue_csv.py).

Nothing here is invented: concern tags CATEGORIZE the brand's own copy by keyword (see CONCERN_KEYWORDS).
"""

import re

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
    "breakout": "blemish",  # "reduce breakouts", "breakout-prone skin" in the brand's benefits copy
    "barrier": "barrier-repair",
    "redness": "redness",
    "sun": "sun-protection",
}

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

# zero-width characters the store's rich-text fields sometimes carry
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍﻿"))


def strip_html(html: str | None) -> str | None:
    if not html:
        return None
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip() or None


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


def parse_ingredient_list(inci_text: str | None) -> list[str]:
    if not inci_text:
        return []
    # INCI lists are comma-separated; strip stray whitespace/newlines and invisible characters.
    raw = [i.translate(_INVISIBLE).strip() for i in inci_text.replace("\n", ",").split(",")]
    return [i for i in raw if i and len(i) > 1]
