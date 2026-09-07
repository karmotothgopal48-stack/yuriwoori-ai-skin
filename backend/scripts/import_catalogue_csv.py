"""
Imports the REAL YuriWoori catalogue from a Shopify product export CSV
(data/products_export.csv). This is the authoritative source: real titles,
prices, images, and â€” critically â€” real INCI ingredient lists straight from
your product admin. Nothing here is invented; unmapped/blank fields stay
blank rather than being guessed.
"""

import csv
import os
import re
import sys
import uuid

sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.db.models import Product, Ingredient, ProductIngredient

CSV_PATH = os.path.join("data", "products_export.csv")

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
# This CATEGORIZES the brand's own real marketing copy â€” it never invents claims.
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


def derive_category_and_step(tags: str) -> tuple[str, str]:
    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    for tag in tag_list:
        if tag in TAG_TO_STEP:
            return tag, TAG_TO_STEP[tag]
    return (tag_list[0] if tag_list else "uncategorized"), "unassigned"


def derive_concern_tags(*texts: str) -> list[str]:
    blob = " ".join(t.lower() for t in texts if t)
    found = set()
    for keyword, tag in CONCERN_KEYWORDS.items():
        if keyword in blob:
            found.add(tag)
    return sorted(found)


def parse_ingredient_list(inci_text: str) -> list[str]:
    if not inci_text:
        return []
    # INCI lists are comma-separated; strip stray whitespace/newlines.
    raw = [i.strip() for i in inci_text.replace("\n", ",").split(",")]
    return [i for i in raw if i and len(i) > 1]


def import_csv():
    db = SessionLocal()
    created, updated, ingredient_links = 0, 0, 0

    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("Title", "").strip():
                continue  # variant/image-only rows for an already-seen product

            handle = row["Handle"]
            title = row["Title"]
            price_raw = row.get("Variant Price", "").strip()
            price = float(price_raw) if price_raw else None
            image_url = row.get("Image Src") or None
            tags = row.get("Tags", "")
            body = strip_html(row.get("Body (HTML)"))
            chips = row.get("chips (product.metafields.custom.chips)", "")
            benefits = row.get("benefits (product.metafields.custom.benefits)", "")
            keybenefit = row.get("keybenefit (product.metafields.custom.keybenefit)", "")
            inci = row.get("inci (product.metafields.custom.inci)", "")

            category, routine_step = derive_category_and_step(tags)
            concern_tags = derive_concern_tags(title, chips, benefits, keybenefit)

            existing = db.query(Product).filter(Product.shopify_product_id == handle).first()
            values = dict(
                name=title,
                price=price,
                currency="INR",
                image_url=image_url,
                category=category,
                routine_step=routine_step,
                description=body or keybenefit,
                product_url=f"https://yuriwoori.com/products/{handle}",
                concern_tags=concern_tags,
                active=True,
            )

            if existing:
                for k, v in values.items():
                    setattr(existing, k, v)
                product = existing
                updated += 1
            else:
                product = Product(shopify_product_id=handle, **values)
                db.add(product)
                created += 1

            db.flush()  # ensure product.id is available

            for ingredient_name in parse_ingredient_list(inci):
                ingredient = db.query(Ingredient).filter(Ingredient.name == ingredient_name).first()
                if not ingredient:
                    ingredient = Ingredient(name=ingredient_name, inci_name=ingredient_name)
                    db.add(ingredient)
                    db.flush()

                link = (
                    db.query(ProductIngredient)
                    .filter(
                        ProductIngredient.product_id == product.id,
                        ProductIngredient.ingredient_id == ingredient.id,
                    )
                    .first()
                )
                if not link:
                    db.add(ProductIngredient(product_id=product.id, ingredient_id=ingredient.id))
                    ingredient_links += 1

    db.commit()
    db.close()
    print(f"Import complete: {created} products created, {updated} updated, {ingredient_links} ingredient links added.")


if __name__ == "__main__":
    import_csv()

