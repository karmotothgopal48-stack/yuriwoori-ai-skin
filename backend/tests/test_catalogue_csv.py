"""Tests for the CSV-backed catalogue and recommender. No database or network needed.

Run from the backend folder:  python -m pytest tests -q
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient

from app.main import app
from app.services.catalogue_csv import active_concerns, derive_concern_tags, load_catalogue, recommend

client = TestClient(app)

BALANCED = dict(hydration=80, oiliness=20, redness=10, pigmentation=10, blemish_index=5, pore_visibility=10)
CONCERNED = dict(hydration=30, oiliness=20, redness=55, pigmentation=50, blemish_index=5, pore_visibility=60)


def test_catalogue_loads_priced_active_products():
    products = load_catalogue()
    assert len(products) > 10
    assert len({p.handle for p in products}) == len(products)


def test_concern_keywords_match_at_word_start_only():
    assert "hydration" in derive_concern_tags("Aqua Hyaluronic Moisture Cream")
    assert "uneven-tone" not in derive_concern_tags("seven day kit")  # "even" inside "seven"


def test_zero_hydration_counts_as_a_concern():
    assert "hydration" in active_concerns({"hydration": 0.0})


def test_balanced_skin_gets_no_recommendations():
    concerns, recs = recommend(BALANCED)
    assert concerns == {} and recs == []


def test_recommendations_match_real_concerns_and_respect_step_cap():
    concerns, recs = recommend(CONCERNED, limit_per_step=1)
    assert recs
    steps = [r["product"].routine_step for r in recs]
    assert len(steps) == len(set(steps))
    for r in recs:
        assert r["product"].routine_step != "bundle" and r["product"].price
        assert set(r["matched_concerns"]) <= set(concerns)
        assert set(r["matched_concerns"]) <= set(r["product"].concern_tags)


def test_recommendations_are_ranked_best_first():
    _, recs = recommend(CONCERNED)
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True)


def test_api_recommendations_from_metrics():
    r = client.get("/v1/catalogue/recommendations", params=CONCERNED)
    assert r.status_code == 200
    body = r.json()
    assert body["active_concerns"] and body["recommendations"]
    assert [x["rank"] for x in body["recommendations"]] == list(range(1, len(body["recommendations"]) + 1))


def test_api_recommendations_requires_scan_or_metrics():
    assert client.get("/v1/catalogue/recommendations").status_code == 400


def test_api_rejects_out_of_range_metric():
    assert client.get("/v1/catalogue/recommendations", params={"redness": 150}).status_code == 422


def test_api_products_filter_and_detail():
    r = client.get("/v1/catalogue/products", params={"step": "cleanse"})
    assert r.status_code == 200 and r.json()
    assert all(p["routine_step"] == "cleanse" for p in r.json())
    handle = r.json()[0]["handle"]
    assert client.get(f"/v1/catalogue/products/{handle}").json()["handle"] == handle
    assert client.get("/v1/catalogue/products/does-not-exist").status_code == 404
