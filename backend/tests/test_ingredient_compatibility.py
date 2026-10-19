"""check_routine_compatibility: interactions are found in either ingredient order, each ingredient pair once,
with a fixed number of queries (it used to issue one query per ingredient pair, several seconds per routine)."""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.models import IngredientInteraction, ProductIngredient
from app.services.ingredient_compatibility import check_routine_compatibility


class _Session:
    """Returns the given rows per model and counts queries (filters are applied by the real DB)."""

    def __init__(self, rows):
        self.rows, self.queries = rows, 0

    def query(self, model):
        self.queries += 1
        rows = self.rows[model]
        return SimpleNamespace(filter=lambda *_: SimpleNamespace(all=lambda: rows))


def link(product, ingredient):
    return SimpleNamespace(product_id=product, ingredient_id=ingredient)


def interaction(a, b, kind="avoid", text="note"):
    return SimpleNamespace(ingredient_a_id=a, ingredient_b_id=b, relationship_type=SimpleNamespace(value=kind), explanation=text)


def test_finds_interactions_in_either_order_once_per_pair():
    db = _Session({
        ProductIngredient: [link("p1", "retinol"), link("p2", "aha"), link("p3", "aha"), link("p3", "niacinamide")],
        IngredientInteraction: [interaction("aha", "retinol", "avoid", "too strong together")],
    })
    flags = check_routine_compatibility(db, ["p1", "p2", "p3"])
    assert flags == [{"product_id_a": "p1", "product_id_b": "p2", "relationship_type": "avoid", "explanation": "too strong together"}]
    assert db.queries == 2


def test_no_products_or_no_interactions():
    assert check_routine_compatibility(_Session({}), []) == []
    db = _Session({ProductIngredient: [link("p1", "a"), link("p2", "b")], IngredientInteraction: []})
    assert check_routine_compatibility(db, ["p1", "p2"]) == []
