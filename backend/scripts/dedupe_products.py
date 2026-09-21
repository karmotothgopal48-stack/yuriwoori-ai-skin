"""
One-time cleanup: Step 11's scrape and Step 12's CSV import created separate
rows for the same real product (different shopify_product_id formats).
Keeps whichever row has real ingredient links (the CSV-sourced one) and
removes the other, re-pointing any recommendations/routine_steps/cart_items
that referenced the duplicate first.
"""

import sys
import os
sys.path.append(os.getcwd())

from collections import defaultdict
from app.db.session import SessionLocal
from app.db.models import Product, ProductIngredient, Recommendation, RoutineStep, CartItem


def dedupe():
    db = SessionLocal()
    by_name = defaultdict(list)
    for p in db.query(Product).all():
        by_name[p.name].append(p)

    removed = 0
    for name, group in by_name.items():
        if len(group) < 2:
            continue

        # Prefer the row that has real ingredient links.
        with_ingredients = [
            p for p in group if db.query(ProductIngredient).filter(ProductIngredient.product_id == p.id).first()
        ]
        keeper = with_ingredients[0] if with_ingredients else group[0]
        duplicates = [p for p in group if p.id != keeper.id]

        for dup in duplicates:
            db.query(Recommendation).filter(Recommendation.product_id == dup.id).update({"product_id": keeper.id})
            db.query(RoutineStep).filter(RoutineStep.product_id == dup.id).update({"product_id": keeper.id})
            db.query(CartItem).filter(CartItem.product_id == dup.id).update({"product_id": keeper.id})
            db.query(ProductIngredient).filter(ProductIngredient.product_id == dup.id).delete()
            db.delete(dup)
            removed += 1

    db.commit()
    db.close()
    print(f"Removed {removed} duplicate product rows.")


if __name__ == "__main__":
    dedupe()