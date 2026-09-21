"""
Builds real vector embeddings from the real, imported catalogue
(products + ingredients). Source text is the product's/ingredient's own
real name, category, concern tags, and description — nothing generated.
Run after every catalogue import/update: python scripts/build_embeddings.py
"""

import sys
import os

sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.db.models import Product, Ingredient, ProductEmbedding, IngredientEmbedding
from app.services.embeddings import embed_text


def build():
    db = SessionLocal()

    products = db.query(Product).filter(Product.active == True).all()  # noqa: E712
    for p in products:
        source_text = (
            f"{p.name}. Category: {p.category}. Routine step: {p.routine_step}. "
            f"Concerns addressed: {', '.join(p.concern_tags or [])}. "
            f"{p.description or ''}"
        ).strip()
        vector = embed_text(source_text)

        existing = db.get(ProductEmbedding, p.id)
        if existing:
            existing.embedding = vector
            existing.source_text = source_text
        else:
            db.add(ProductEmbedding(product_id=p.id, embedding=vector, source_text=source_text))

    ingredients = db.query(Ingredient).all()
    for i in ingredients:
        source_text = f"{i.name}. INCI: {i.inci_name or i.name}."
        vector = embed_text(source_text)

        existing = db.get(IngredientEmbedding, i.id)
        if existing:
            existing.embedding = vector
            existing.source_text = source_text
        else:
            db.add(IngredientEmbedding(ingredient_id=i.id, embedding=vector, source_text=source_text))

    db.commit()
    db.close()
    print(f"Embedded {len(products)} products and {len(ingredients)} ingredients.")


if __name__ == "__main__":
    build()