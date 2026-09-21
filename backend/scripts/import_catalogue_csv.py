"""
Imports the REAL YuriWoori catalogue from a Shopify product export CSV
(data/products_export.csv). This is the authoritative source: real titles,
prices, images, and — critically — real INCI ingredient lists straight from
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

from app.services.catalogue_csv import (  # shared with the catalogue API
    derive_category_and_step,
    derive_concern_tags,
    is_bundle,
    parse_ingredient_list,
    strip_html,
)


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

            category, routine_step = derive_category_and_step(tags, handle, title)
            if is_bundle(handle, tags, price):
                category, routine_step = "bundle", "bundle"
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
                chips=[c.strip() for c in chips.split(",") if c.strip()],
                benefits_raw=benefits or None,
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

