from sqlalchemy.orm import Session
from app.db.models import ProductIngredient, IngredientInteraction


def check_routine_compatibility(db: Session, product_ids: list) -> list[dict]:
    """Given a list of product IDs in one routine, return every real
    interaction between ingredients those products actually contain."""

    product_ingredients: dict = {}
    for pid in product_ids:
        links = db.query(ProductIngredient).filter(ProductIngredient.product_id == pid).all()
        product_ingredients[pid] = {link.ingredient_id for link in links}

    flags = []
    seen_pairs = set()
    product_id_list = list(product_ingredients.keys())

    for i, pid_a in enumerate(product_id_list):
        for pid_b in product_id_list[i + 1 :]:
            for ing_a_id in product_ingredients[pid_a]:
                for ing_b_id in product_ingredients[pid_b]:
                    pair_key = tuple(sorted([str(ing_a_id), str(ing_b_id)]))
                    if pair_key in seen_pairs:
                        continue

                    interaction = (
                        db.query(IngredientInteraction)
                        .filter(
                            (
                                (IngredientInteraction.ingredient_a_id == ing_a_id)
                                & (IngredientInteraction.ingredient_b_id == ing_b_id)
                            )
                            | (
                                (IngredientInteraction.ingredient_a_id == ing_b_id)
                                & (IngredientInteraction.ingredient_b_id == ing_a_id)
                            )
                        )
                        .first()
                    )
                    if interaction:
                        seen_pairs.add(pair_key)
                        flags.append(
                            {
                                "product_id_a": pid_a,
                                "product_id_b": pid_b,
                                "relationship_type": interaction.relationship_type.value,
                                "explanation": interaction.explanation,
                            }
                        )

    return flags