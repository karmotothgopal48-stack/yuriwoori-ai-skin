"""
Face/hand body-part support: which analysis runs, what a hand result contains, and that hand
scans are matched against hand care only (store snapshot catalogue). No database or network needed.
"""

import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import skin_analysis
from app.services.live_catalogue import get_catalogue
from app.services.recommendation import HAND_CATEGORY
from app.services.recommendation import recommend as _recommend
from app.services.skin_analysis import analyze_skin_profile, body_part_of


def _write(tmp_path, name, image):
    path = str(tmp_path / name)
    cv2.imwrite(path, image)
    return path


def _skin_coloured(h=480, w=480):
    """A flat, skin-toned image: passes a colour rule, but contains no face and no hand."""
    image = np.zeros((h, w, 3), dtype=np.uint8)
    image[:] = (140, 170, 215)  # BGR, light skin tone
    return image


def test_body_part_comes_from_the_frame_angle():
    assert body_part_of(["hand"]) == "hand"
    assert body_part_of(["front"]) == "face"
    assert body_part_of([]) == "face"
    assert body_part_of(None) == "face"


def test_skin_coloured_background_is_not_a_face_or_a_hand(tmp_path):
    path = _write(tmp_path, "wall.jpg", _skin_coloured())
    with pytest.raises(ValueError, match="No usable face"):
        analyze_skin_profile([path], "face")
    with pytest.raises(ValueError, match="No hand found"):
        analyze_skin_profile([path], "hand")


def test_hand_detector_model_ships_with_the_backend():
    assert os.path.exists(skin_analysis.HAND_MODEL_PATH)


def test_hand_result_reports_only_hand_metrics(tmp_path, monkeypatch):
    # Detection is the model's job (covered above); here a known hand outline is supplied so the
    # measuring step can be checked on its own.
    image = _skin_coloured()
    rng = np.random.default_rng(0)
    image = np.clip(image.astype(np.int16) + rng.integers(-6, 7, image.shape), 0, 255).astype(np.uint8)
    path = _write(tmp_path, "hand.jpg", image)
    points = np.zeros((21, 2), dtype=np.float32)
    outline = {0: (240, 420), 1: (170, 380), 2: (130, 320), 5: (170, 160), 9: (230, 140), 13: (290, 150), 17: (340, 180)}
    for i, xy in outline.items():
        points[i] = xy
    monkeypatch.setattr(skin_analysis, "_find_hand", lambda bgr: points)

    result = analyze_skin_profile([path], "hand")

    assert result["oiliness"] is None and result["blemish_index"] is None and result["pore_visibility"] is None
    for key in ("hydration", "texture", "redness", "pigmentation", "overall_score"):
        assert 0 <= result[key] <= 100
    assert result["skin_type"] in {"dry", "normal"}
    assert set(result) == {
        "skin_type", "hydration", "oiliness", "texture", "redness", "pigmentation",
        "blemish_index", "pore_visibility", "overall_score",
    }


def recommend(metrics, **kwargs):
    return _recommend(metrics, get_catalogue().products, **kwargs)


def test_hand_scan_recommends_hand_care_only():
    _, ranked = recommend({"hydration": 20.0, "pigmentation": 60.0}, body_part="hand")
    assert ranked, "dry hand skin should match at least one hand cream"
    assert all(item["product"].category == HAND_CATEGORY for item in ranked)


def test_face_scan_recommendations_are_unchanged_by_the_hand_filter():
    metrics = {"hydration": 20.0, "pigmentation": 60.0, "redness": 70.0}
    assert recommend(metrics) == recommend(metrics, body_part="face")
    assert any(item["product"].category != HAND_CATEGORY for item in recommend(metrics)[1])


def test_catalogue_has_hand_care_to_recommend():
    assert any(p.category == HAND_CATEGORY and p.price for p in get_catalogue().products)
