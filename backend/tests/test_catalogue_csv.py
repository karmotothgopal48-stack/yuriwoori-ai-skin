"""Tests for the legacy CSV reader (app/services/catalogue_csv.py), used only by
scripts/import_catalogue_csv.py. The app's catalogue is the live store (see test_catalogue_api.py).

Run from the backend folder:  python -m pytest tests -q
"""

from app.services.catalogue_csv import derive_concern_tags, load_catalogue


def test_catalogue_loads_priced_active_products():
    products = load_catalogue()
    assert len(products) > 10
    assert len({p.handle for p in products}) == len(products)


def test_concern_keywords_match_at_word_start_only():
    assert "hydration" in derive_concern_tags("Aqua Hyaluronic Moisture Cream")
    assert "uneven-tone" not in derive_concern_tags("seven day kit")  # "even" inside "seven"


def test_csv_reader_applies_the_same_rules_as_the_live_catalogue(catalogue):
    """For every product in both, the export and the live store copy give the same step, tags and INCI."""
    for p in load_catalogue():
        live = catalogue.get(p.handle)
        if live is None:
            continue  # no longer sold
        assert (live.routine_step, set(live.concern_tags), list(live.ingredients)) == \
            (p.routine_step, set(p.concern_tags), list(p.ingredients)), p.handle
