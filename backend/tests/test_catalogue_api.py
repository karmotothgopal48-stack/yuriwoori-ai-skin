"""The catalogue API and recommender on the live store catalogue (tests/fixtures/store_snapshot.json,
a capture of yuriwoori.com). No database or network needed."""

from fastapi.testclient import TestClient

from app.main import app
from app.services.recommendation import active_concerns, recommend

client = TestClient(app)

BALANCED = dict(hydration=80, oiliness=20, redness=10, pigmentation=10, blemish_index=5, pore_visibility=10)
CONCERNED = dict(hydration=30, oiliness=20, redness=55, pigmentation=50, blemish_index=5, pore_visibility=60)


def test_zero_hydration_counts_as_a_concern():
    assert "hydration" in active_concerns({"hydration": 0.0})


def test_balanced_skin_gets_no_recommendations(catalogue):
    concerns, recs = recommend(BALANCED, catalogue.products)
    assert concerns == {} and recs == []


def test_recommendations_match_real_concerns_and_respect_step_cap(catalogue):
    concerns, recs = recommend(CONCERNED, catalogue.products, limit_per_step=1)
    assert recs
    steps = [r["product"].routine_step for r in recs]
    assert len(steps) == len(set(steps))
    for r in recs:
        p = r["product"]
        assert p.routine_step != "bundle" and p.price and p.available and p.variant_id
        assert set(r["matched_concerns"]) <= set(concerns)
        assert set(r["matched_concerns"]) <= set(p.concern_tags)


def test_recommendations_are_ranked_best_first(catalogue):
    _, recs = recommend(CONCERNED, catalogue.products)
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True)


def test_only_products_the_store_sells_are_recommended(catalogue):
    _, recs = recommend(CONCERNED, catalogue.products, limit_per_step=10)
    assert {r["product"].handle for r in recs} <= set(catalogue.by_handle)
    assert "hydra-glow-mask-kit" not in catalogue.by_handle  # in the old CSV export, no longer in the store


def test_api_recommendations_from_metrics_carry_live_store_fields():
    r = client.get("/v1/catalogue/recommendations", params=CONCERNED)
    assert r.status_code == 200
    body = r.json()
    assert body["active_concerns"] and body["recommendations"] and body["catalogue_fetched_at"] and body["catalogue_stale"] is False
    assert [x["rank"] for x in body["recommendations"]] == list(range(1, len(body["recommendations"]) + 1))
    first = body["recommendations"][0]
    assert first["product_id"] and first["variant_id"] and first["available"] is True
    assert first["benefits"] and {"icon", "title", "description"} <= set(first["benefits"][0]) and first["ingredients"]
    assert first["product_url"].startswith("https://yuriwoori.com/products/")


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
    assert client.get("/v1/catalogue/products/hydra-glow-mask-kit").status_code == 404  # no longer sold


def test_how_to_use_and_key_benefit_come_from_the_live_product_page(catalogue):
    with_usage = [p for p in catalogue.products if p.how_to_use]
    assert with_usage, "the store's product pages carry How to Use copy for most products"
    assert all("<" not in p.how_to_use for p in with_usage)  # HTML stripped
    r = client.get(f"/v1/catalogue/products/{with_usage[0].handle}").json()
    assert r["how_to_use"] == with_usage[0].how_to_use
    assert "key_benefit" in r


def test_recommendations_expose_usage_fields(catalogue):
    _, ranked = recommend(CONCERNED, catalogue.products)
    r = client.get("/v1/catalogue/recommendations", params=CONCERNED).json()
    assert r["recommendations"] and {"how_to_use", "key_benefit"} <= set(r["recommendations"][0])
    assert len(r["recommendations"]) == len(ranked)
