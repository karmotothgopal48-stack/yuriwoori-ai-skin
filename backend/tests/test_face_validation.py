"""
Full-face validation, the landmark-based analysis region, and the Typical / Benchmark values sent to
the results screens. Uses the brand's own campaign portrait from the frontend assets (a frontal,
complete face); test variants (cropped, padded, rotated, doubled) are made from it at runtime.
"""

import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import skin_analysis
from app.services.benchmark import BENCHMARK_VERSION, FACE_BENCHMARK, benchmark_for
from app.services.skin_analysis import analyze_skin_profile

PORTRAIT = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "public", "assets", "permission-portrait.webp"
)
METRICS = ("hydration", "oiliness", "texture", "redness", "pigmentation", "blemish_index", "pore_visibility")

needs_portrait = pytest.mark.skipif(not os.path.exists(PORTRAIT), reason="frontend campaign portrait not available")


@pytest.fixture(scope="module")
def portrait():
    return cv2.imread(PORTRAIT)


def _analyze(tmp_path, image, name="photo.jpg"):
    path = str(tmp_path / name)
    cv2.imwrite(path, image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return analyze_skin_profile([path], "face")


def test_face_model_ships_with_the_backend():
    assert os.path.exists(skin_analysis.FACE_MODEL_PATH)


@needs_portrait
def test_complete_face_gets_all_seven_metrics(tmp_path, portrait):
    result = _analyze(tmp_path, portrait)
    for key in METRICS:
        assert 0 <= result[key] <= 100, key
    assert result["skin_type"] in {"oily", "dry", "combination", "normal"}


@needs_portrait
def test_scores_do_not_depend_on_photo_resolution(tmp_path, portrait):
    # Before the fixed-scale region, texture for one test face went 0 -> 89 between 1x and 2x.
    base = _analyze(tmp_path, portrait, "1x.jpg")
    bigger = _analyze(tmp_path, cv2.resize(portrait, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC), "1.5x.jpg")
    for key in METRICS:
        assert abs(base[key] - bigger[key]) <= 3, (key, base[key], bigger[key])


@needs_portrait
def test_two_faces_are_rejected(tmp_path, portrait):
    with pytest.raises(ValueError, match="Only one face"):
        _analyze(tmp_path, np.hstack([portrait, portrait]))


@needs_portrait
def test_forehead_only_is_rejected(tmp_path, portrait):
    h = portrait.shape[0]
    with pytest.raises(ValueError, match="No usable face"):
        _analyze(tmp_path, portrait[: int(h * 0.30)])


@needs_portrait
def test_half_face_outside_the_photo_is_rejected(tmp_path, portrait):
    w = portrait.shape[1]
    with pytest.raises(ValueError, match="No usable face|Centre your full face"):
        _analyze(tmp_path, portrait[:, int(w * 0.52):])


@needs_portrait
def test_face_too_far_is_rejected(tmp_path, portrait):
    padded = cv2.copyMakeBorder(portrait, 1500, 1500, 1200, 1200, cv2.BORDER_REPLICATE)
    with pytest.raises(ValueError, match="Move slightly closer"):
        _analyze(tmp_path, cv2.resize(padded, None, fx=0.35, fy=0.35, interpolation=cv2.INTER_AREA))


@needs_portrait
def test_tilted_face_is_rejected(tmp_path, portrait):
    h, w = portrait.shape[:2]
    rotation = cv2.getRotationMatrix2D((w / 2, h * 0.4), 35, 1.0)
    with pytest.raises(ValueError, match="Keep your head straight"):
        _analyze(tmp_path, cv2.warpAffine(portrait, rotation, (w, h), borderMode=cv2.BORDER_REPLICATE))


def test_face_benchmark_covers_all_seven_metrics_with_fixed_values():
    benchmark = benchmark_for("face")
    assert set(benchmark) == set(METRICS)
    assert all(0 <= v <= 100 for v in benchmark.values())
    assert benchmark_for("face") == benchmark == FACE_BENCHMARK  # same values for every scan
    assert BENCHMARK_VERSION


def test_no_hand_benchmark_is_configured_yet():
    assert benchmark_for("hand") == {}


def test_benchmark_is_separate_from_product_thresholds():
    # The benchmark is display-only; recommendations still use their own thresholds.
    from app.services.recommendation import CONCERN_RULES, HYDRATION_MIN
    assert HYDRATION_MIN == 45 and {t for _, t, _, _ in CONCERN_RULES} == {40, 55}
    assert FACE_BENCHMARK["hydration"] != HYDRATION_MIN
