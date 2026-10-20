"""
Scan measurements -> concerns -> recommendations -> routine, against the REAL store catalogue
(tests/fixtures/store_snapshot.json, a capture of yuriwoori.com read through app/services/live_catalogue.py).
No database or network is needed.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.catalogue_rules import derive_concern_tags
from app.services.live_catalogue import get_catalogue
from app.services.recommendation import active_concerns
from app.services.routine_builder import build_routine

BALANCED = dict(hydration=84.3, texture=98.3, oiliness=0.0, redness=11.1, pigmentation=20.9, pore_visibility=2.7, blemish_index=4.4)


def scan(**overrides):
    return {**BALANCED, **overrides}


def products():
    return get_catalogue().products


def recommend(metrics, *args, **kwargs):
    from app.services.recommendation import recommend as live_recommend
    return live_recommend(metrics, products(), *args, **kwargs)


def routine_for(metrics):
    return build_routine(SimpleNamespace(**metrics), products())


def test_uneven_tone_scan_reaches_the_recommender_and_routine():
    metrics = scan(pigmentation=63.0)
    assert set(active_concerns(metrics)) == {"brightening", "uneven-tone"}
    concerns, ranked = recommend(metrics)
    assert ranked and all({"brightening", "uneven-tone"} & set(r["product"].concern_tags) for r in ranked)
    routine = routine_for(metrics)
    assert routine["AM"] and routine["PM"]
    for step in routine["AM"] + routine["PM"]:
        assert {"brightening", "uneven-tone"} & set(step["product"].concern_tags)


def test_dryness_scan_matches_hydration_products():
    metrics = scan(hydration=30.0)
    assert set(active_concerns(metrics)) == {"hydration"}
    _, ranked = recommend(metrics)
    assert ranked and all("hydration" in r["product"].concern_tags for r in ranked)
    assert routine_for(metrics)["AM"]


def test_breakout_scan_matches_products_whose_official_copy_mentions_breakouts():
    metrics = scan(blemish_index=60.0)
    assert set(active_concerns(metrics)) == {"blemish"}
    _, ranked = recommend(metrics)
    handles = {r["product"].handle for r in ranked}
    # "reduce breakouts" / "breakout-prone skin" in their benefits copy
    assert "bubble-soothing-toner" in handles
    assert routine_for(metrics)["AM"], "a blemish concern must produce at least one routine step"


def test_breakout_keyword_maps_to_the_blemish_concern():
    assert "blemish" in derive_concern_tags("helps reduce breakouts")
    assert "blemish" in derive_concern_tags("built for breakout-prone skin")


def test_balanced_scan_gets_no_targeted_products():
    assert active_concerns(BALANCED) == {}
    assert recommend(BALANCED) == ({}, [])
    assert routine_for(BALANCED) == {"AM": [], "PM": []}


@pytest.mark.parametrize("metric,value,tag", [
    ("redness", 41, "redness"), ("pore_visibility", 41, "pore-visibility"), ("oiliness", 56, "oiliness"),
    ("hydration", 44, "hydration"), ("pigmentation", 41, "uneven-tone"), ("blemish_index", 41, "blemish"),
])
def test_every_concern_threshold_is_deterministic(metric, value, tag):
    assert tag in active_concerns(scan(**{metric: value}))
    edge = {"hydration": 45}.get(metric, 55 if metric == "oiliness" else 40)
    assert tag not in active_concerns(scan(**{metric: edge}))  # exactly at the level: not a concern


def test_incomplete_analysis_is_detected_per_scan_type():
    from app.services.skin_analysis import missing_measurements
    face = SimpleNamespace(**BALANCED)
    assert missing_measurements(face, "face") == []
    assert missing_measurements(SimpleNamespace(**{**BALANCED, "pigmentation": None}), "face") == ["pigmentation"]
    # a hand scan legitimately has no oil/pore/blemish measures
    hand = SimpleNamespace(**{**BALANCED, "oiliness": None, "pore_visibility": None, "blemish_index": None})
    assert missing_measurements(hand, "hand") == []
    assert missing_measurements(SimpleNamespace(**{**BALANCED, "redness": None}), "hand") == ["redness"]


def test_recommendations_response_states_the_verdict_explicitly():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    balanced = client.get("/v1/catalogue/recommendations", params={k: v for k, v in BALANCED.items() if k != "texture"}).json()
    assert balanced["analysis_status"] == "balanced" and balanced["active_concerns"] == {} and balanced["recommendations"] == []
    tone = client.get("/v1/catalogue/recommendations", params={"pigmentation": 63, "hydration": 84}).json()
    assert tone["analysis_status"] == "concerns" and "uneven-tone" in tone["active_concerns"] and tone["recommendations"]


def test_maintenance_routine_uses_real_general_care_products():
    from app.services.routine_builder import build_maintenance_routine
    routine = build_maintenance_routine(products(), "face")
    am = [(s["step"], s["product"].handle) for s in routine["AM"]]
    pm = [(s["step"], s["product"].handle) for s in routine["PM"]]
    assert [s for s, _ in am] == ["cleanse", "tone", "moisturize", "protect"]
    assert [s for s, _ in pm] == ["cleanse", "tone", "moisturize"]  # no treat; protect in the morning only
    catalogue = {p.handle for p in products()}
    for step in routine["AM"] + routine["PM"]:
        p = step["product"]
        assert p.handle in catalogue and p.category != "handcream" and p.available
        if step["step"] == "protect":
            assert "sun-protection" in p.concern_tags
        else:
            assert {"hydration", "barrier-repair", "soothing"} & set(p.concern_tags)
    assert dict(am)["cleanse"] == dict(pm)["cleanse"]  # same product morning and evening -> one merged card


def test_maintenance_routine_for_a_hand_scan_is_hand_care_only():
    from app.services.routine_builder import build_maintenance_routine
    routine = build_maintenance_routine(products(), "hand")
    steps = routine["AM"] + routine["PM"]
    assert steps and all(s["product"].category == "handcream" for s in steps)


def test_maintenance_routine_needs_the_owner_session():
    from fastapi.testclient import TestClient
    from app.main import app
    assert TestClient(app).get("/v1/scans/00000000-0000-0000-0000-000000000001/maintenance-routine").status_code == 401
