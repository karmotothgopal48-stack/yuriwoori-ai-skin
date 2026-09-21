"""Unit tests for pure backend logic. No database, network, or OpenCV required.

Run from the backend folder:  python -m pytest tests -q
"""

import base64
import os
import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import Settings
from app.schemas import FrameUploadRequest
from app.services.cv_quality import analyze_frame
from app.services.product_detail import parse_benefits
from app.services.progress import build_progress_series
from app.services.shopping_agent import extract_budget


# ---------- config / CORS ----------

def test_cors_origins_include_frontend_port_2999():
    origins = Settings(_env_file=None).cors_origins
    assert "http://localhost:2999" in origins
    assert "http://127.0.0.1:2999" in origins


def test_cors_origins_parses_comma_list_and_strips_slashes():
    s = Settings(_env_file=None, frontend_origin="http://a.test/, http://b.test")
    assert s.cors_origins == ["http://a.test", "http://b.test"]


# ---------- request validation ----------

def test_frame_angle_rejects_path_traversal():
    with pytest.raises(ValidationError):
        FrameUploadRequest(angle="../../evil", image_base64="AAAA")


def test_frame_angle_accepts_normal_names():
    assert FrameUploadRequest(angle="front", image_base64="AAAA").angle == "front"
    assert FrameUploadRequest(angle="left_45", image_base64="AAAA").angle == "left_45"


# ---------- frame quality gate ----------

def test_analyze_frame_rejects_non_jpeg():
    result = analyze_frame(base64.b64encode(b"not a jpeg" * 1000).decode())
    assert result["passed"] is False
    assert result["quality_score"] == 0.0


def test_analyze_frame_rejects_tiny_payload():
    assert analyze_frame("AAAA")["passed"] is False


# ---------- product benefits parsing ----------

def test_parse_benefits_reads_icon_title_description():
    raw = "A|Title One|Desc one\nB|Title Two|Desc two"
    assert parse_benefits(raw) == [
        {"icon": "A", "title": "Title One", "description": "Desc one"},
        {"icon": "B", "title": "Title Two", "description": "Desc two"},
    ]


def test_parse_benefits_empty_or_malformed():
    assert parse_benefits(None) == []
    assert parse_benefits("") == []
    assert parse_benefits("only|two") == []


# ---------- budget extraction ----------

@pytest.mark.parametrize(
    "text,expected",
    [("2k budget", 2000.0), ("under 1500", 1500.0), ("Rs. 2,500", 2500.0), ("2000 rupees", 2000.0)],
)
def test_extract_budget(text, expected):
    assert extract_budget(text) == expected


def test_extract_budget_none_when_missing():
    assert extract_budget("build me a routine") is None


# ---------- progress ----------

def _snap(day, **kw):
    base = dict(hydration=50, oiliness=50, texture=50, redness=50, pigmentation=50, blemish_index=50)
    base.update(kw)
    return SimpleNamespace(day_offset=day, **base)


def test_progress_reports_only_meaningful_changes():
    result = build_progress_series([_snap(0), _snap(14, hydration=62, redness=44, oiliness=52)])
    changes = {c["metric"]: c["direction"] for c in result["meaningful_changes"]}
    assert changes == {"hydration": "improved", "redness": "improved"}  # oiliness delta is noise


def test_progress_empty():
    assert build_progress_series([]) == {"snapshots": [], "meaningful_changes": []}
