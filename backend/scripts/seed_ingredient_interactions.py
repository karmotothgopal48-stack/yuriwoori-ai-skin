import sys
import os

sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.db.models import Ingredient, IngredientInteraction, IngredientInteractionType
from app.services.ingredient_interactions_seed import SEED_INTERACTIONS


def find_ingredient(db, name: str) -> Ingredient | None:
    return db.query(Ingredient).filter(Ingredient.name.ilike(name)).first()


def seed():
    db = SessionLocal()
    created, skipped = 0, 0

    for entry in SEED_INTERACTIONS:
        ing_a = find_ingredient(db, entry["a"])
        ing_b = find_ingredient(db, entry["b"])

        if not ing_a or not ing_b:
            missing = entry["a"] if not ing_a else entry["b"]
            print(f"Skipped '{entry['a']}' + '{entry['b']}' — '{missing}' not in current catalogue yet.")
            skipped += 1
            continue

        existing = (
            db.query(IngredientInteraction)
            .filter(
                IngredientInteraction.ingredient_a_id == ing_a.id,
                IngredientInteraction.ingredient_b_id == ing_b.id,
            )
            .first()
        )
        if existing:
            continue

        db.add(
            IngredientInteraction(
                ingredient_a_id=ing_a.id,
                ingredient_b_id=ing_b.id,
                relationship_type=IngredientInteractionType[entry["relationship_type"]],
                explanation=entry["explanation"],
            )
        )
        created += 1

    db.commit()
    db.close()
    print(f"Done: {created} interactions created, {skipped} skipped (ingredient not in catalogue).")


if __name__ == "__main__":
    seed()
    