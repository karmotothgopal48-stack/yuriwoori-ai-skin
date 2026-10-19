"""
The products table as a record of live products (app/services/product_records.py), and saved routines that
follow the live catalogue. Runs on an in-memory stand-in for the database session: no database needed.
"""

import uuid
from dataclasses import replace
from types import SimpleNamespace

from app.db.models import Ingredient, Product, ProductIngredient, Routine, RoutineStep
from app.services import product_records
from app.services.product_records import ensure_product_rows, mark_unlisted_inactive, save_routine_if_changed
from app.services.routine_builder import build_routine


class FakeSession:
    """Just enough of a SQLAlchemy session: query(Model).filter(...).all()/.first() return every stored row of
    that model (the code under test re-checks handles/ids itself), add/delete/flush keep rows and ids."""

    def __init__(self):
        self.rows: dict[type, list] = {}

    def query(self, model):
        rows = self.rows.setdefault(model, [])
        return SimpleNamespace(filter=lambda *_: SimpleNamespace(all=lambda: list(rows), first=lambda: rows[0] if rows else None))

    def add(self, obj):
        self.rows.setdefault(type(obj), []).append(obj)

    def delete(self, obj):
        self.rows[type(obj)].remove(obj)

    def flush(self):
        for rows in self.rows.values():
            for obj in rows:
                if getattr(obj, "id", "n/a") is None:
                    obj.id = uuid.uuid4()


def test_live_products_are_recorded_by_handle_and_refreshed(catalogue):
    db = FakeSession()
    toner = catalogue.get("bubble-soothing-toner")
    rows = ensure_product_rows(db, [toner, toner])
    row = rows["bubble-soothing-toner"]
    assert len(db.rows[Product]) == 1 and row.shopify_product_id == toner.handle
    assert (row.price, row.shopify_variant_id, row.product_url) == (toner.price, toner.variant_gid, toner.product_url)
    assert row.active and row.concern_tags == list(toner.concern_tags)

    cheaper = replace(toner, price=toner.price - 100)  # the store changed the price
    again = ensure_product_rows(db, [cheaper])
    assert again["bubble-soothing-toner"] is row and row.price == toner.price - 100 and len(db.rows[Product]) == 1


def test_ingredient_links_follow_the_live_inci_list(catalogue):
    db = FakeSession()
    toner = catalogue.get("bubble-soothing-toner")
    row = ensure_product_rows(db, [toner])[toner.handle]
    names = {i.id: i.name for i in db.rows[Ingredient]}
    assert sorted(names[link.ingredient_id] for link in db.rows[ProductIngredient]) == sorted(toner.ingredients)

    reformulated = replace(toner, ingredients=("Water", "Centella Asiatica Extract"))
    ensure_product_rows(db, [reformulated])
    names = {i.id: i.name for i in db.rows[Ingredient]}
    assert sorted(names[link.ingredient_id] for link in db.rows[ProductIngredient] if link.product_id == row.id) == \
        ["Centella Asiatica Extract", "Water"]


def test_products_the_store_no_longer_lists_are_kept_but_inactive(catalogue):
    db = FakeSession()
    ensure_product_rows(db, [catalogue.get("bubble-soothing-toner")])
    old = Product(shopify_product_id="hydra-glow-mask-kit", name="Old kit", active=True)
    db.add(old)
    assert mark_unlisted_inactive(db, catalogue) == 1
    assert old in db.rows[Product] and old.active is False  # not deleted: old records may point at it


DRY = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), hydration=30.0, oiliness=0.0, texture=90.0, redness=10.0,
                      pigmentation=10.0, blemish_index=5.0, pore_visibility=5.0)


def _save(db, products, monkeypatch, latest):
    built = build_routine(DRY, products)
    rows = ensure_product_rows(db, [p["product"] for period in ("AM", "PM") for p in built[period]])
    monkeypatch.setattr(product_records, "latest_routine", lambda _db, _pid: latest)
    return built, rows, save_routine_if_changed(db, DRY, built, rows)


def _as_saved(routine, db):
    routine.steps = [s for s in db.rows.get(RoutineStep, []) if s.routine_id == routine.id]
    return routine


def test_a_routine_is_saved_again_only_when_the_live_catalogue_changes_it(catalogue, monkeypatch):
    db = FakeSession()
    built, rows, first = _save(db, catalogue.products, monkeypatch, latest=None)
    assert built["AM"] and len(db.rows[Routine]) == 1
    assert {s.product_id for s in db.rows[RoutineStep]} == {rows[p["product"].handle].id for period in ("AM", "PM") for p in built[period]}

    # same live result: no new version
    _, _, same = _save(db, catalogue.products, monkeypatch, latest=_as_saved(first, db))
    assert same is first and len(db.rows[Routine]) == 1

    # a price change alone doesn't change the routine
    repriced = [replace(p, price=p.price + 1) if p.price else p for p in catalogue.products]
    _, _, same = _save(db, repriced, monkeypatch, latest=_as_saved(first, db))
    assert same is first and len(db.rows[Routine]) == 1

    # the morning cleanser sells out: the routine is rebuilt without it and saved as a new version
    cleanser = next(p["product"] for p in built["AM"] if p["step"] == "cleanse")
    sold_out = [replace(p, available=False) if p.handle == cleanser.handle else p for p in catalogue.products]
    new_built, _, second = _save(db, sold_out, monkeypatch, latest=_as_saved(first, db))
    assert second is not first and len(db.rows[Routine]) == 2  # the first version is kept as history
    assert cleanser.handle not in {p["product"].handle for period in ("AM", "PM") for p in new_built[period]}
