from sqlalchemy.orm import Session
from app.db.models import ProductIngredient, IngredientInteraction


def check_routine_compatibility(db: Session, product_ids: list) -> list[dict]:
    """Given a list of product IDs in one routine, return every real
    interaction between ingredients those products actually contain.

    Two queries (the routine's ingredient links, then the interactions among those ingredients),
    matched in memory - one query per ingredient pair took several seconds per routine."""

    product_ingredients: dict = {pid: set() for pid in product_ids}
    if not product_ids:
        return []
    for link in db.query(ProductIngredient).filter(ProductIngredient.product_id.in_(product_ids)).all():
        product_ingredients[link.product_id].add(link.ingredient_id)

    all_ingredients = set().union(*product_ingredients.values())
    interactions: dict = {}
    if all_ingredients:
        rows = (
            db.query(IngredientInteraction)
            .filter(
                IngredientInteraction.ingredient_a_id.in_(all_ingredients),
                IngredientInteraction.ingredient_b_id.in_(all_ingredients),
            )
            .all()
        )
        for row in rows:
            interactions.setdefault((row.ingredient_a_id, row.ingredient_b_id), row)

    def interaction_between(a, b):
        return interactions.get((a, b)) or interactions.get((b, a))

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

                    interaction = interaction_between(ing_a_id, ing_b_id)
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
