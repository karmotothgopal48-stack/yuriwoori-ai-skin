"""
No selfie storage: scan photos are checked and analysed in memory, never written to disk, the database or S3.
Runs the real scan endpoints on the real database (rolled back; skipped without PostgreSQL). Any attempt to
write a photo fails the test: the storage module, cv2.imwrite and temp files are all booby-trapped, and the
upload folder is compared before and after.
"""

import base64
import os
import tempfile

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import scans as scans_endpoint
from app.db.models import ScanFrame, SkinProfile
from app.main import app
from app.services import skin_analysis, storage
from conftest import make_scan

client = TestClient(app)
METRICS = dict(skin_type="normal", hydration=60.0, oiliness=20.0, texture=80.0, redness=20.0, pigmentation=20.0,
               blemish_index=5.0, pore_visibility=10.0, overall_score=75.0)


def jpeg_base64(seed=1, size=720) -> str:
    """A detailed, well-lit JPEG that passes the server's quality check (no face in it)."""
    rng = np.random.default_rng(seed)
    image = rng.integers(60, 230, (size, size, 3), dtype=np.uint8)
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return "data:image/jpeg;base64," + base64.b64encode(data.tobytes()).decode()


def files_under(folder):
    return {os.path.join(root, f) for root, _, names in os.walk(folder) for f in names} if os.path.isdir(folder) else set()


@pytest.fixture
def no_writes(monkeypatch):
    """Fail on any attempt to store a photo; afterwards, the upload folder must be unchanged."""
    def forbidden(*args, **kwargs):
        raise AssertionError("a scan photo was about to be written")
    monkeypatch.setattr(cv2, "imwrite", forbidden)
    for name in ("mkstemp", "NamedTemporaryFile", "TemporaryFile", "SpooledTemporaryFile"):
        monkeypatch.setattr(tempfile, name, forbidden)
    before = files_under(storage.UPLOAD_DIR)
    yield
    assert files_under(storage.UPLOAD_DIR) == before, "files were added to the upload folder"


@pytest.fixture
def new_scan(db):
    user = make_scan(db, email_prefix="no-selfie-storage")  # a signed-up user (their own earlier scan is irrelevant)
    r = client.post("/v1/scans", headers=user.headers)
    assert r.status_code == 200, r.text
    return {"id": r.json()["scan_id"], "headers": user.headers}


def test_in_memory_decoding_of_a_photo():
    image = jpeg_base64()
    bgr = skin_analysis._load_bgr(base64.b64decode(image.split(",", 1)[1]))
    assert bgr.shape == (720, 720, 3)
    with pytest.raises(ValueError):
        skin_analysis._load_bgr(b"not an image")


def test_a_scan_is_checked_and_analysed_without_storing_the_photo(db, new_scan, no_writes, monkeypatch):
    image = jpeg_base64()
    analysed = []
    monkeypatch.setattr(scans_endpoint, "analyze_skin_profile", lambda frames, part: (analysed.append((frames, part)), METRICS)[1])

    r = client.post(f"/v1/scans/{new_scan['id']}/frames", headers=new_scan["headers"], json={"angle": "front", "image_base64": image})
    assert r.status_code == 200 and r.json()["passed"] is True, r.text
    frame = db.query(ScanFrame).filter(ScanFrame.scan_id == new_scan["id"]).one()
    assert frame.storage_key == "not-stored" and frame.quality_score is not None  # scores kept, photo not

    url = f"/v1/scans/{new_scan['id']}/analyze"
    assert client.post(url, headers=new_scan["headers"]).status_code == 400  # without the photo: nothing to analyse
    assert client.post(url, headers=new_scan["headers"], json={"angle": "hand", "image_base64": image}).status_code == 400

    r = client.post(url, headers=new_scan["headers"], json={"angle": "front", "image_base64": image})
    assert r.status_code == 200 and r.json()["hydration"] == 60.0, r.text
    [(frames, part)] = analysed
    assert part == "face" and len(frames) == 1 and isinstance(frames[0], bytes)  # analysed from memory, not a path
    assert db.query(SkinProfile).filter(SkinProfile.scan_id == new_scan["id"]).count() == 1  # results ARE saved

    # asking again returns the saved result without needing (or storing) the photo
    again = client.post(url, headers=new_scan["headers"])
    assert again.status_code == 200 and again.json()["hydration"] == 60.0 and len(analysed) == 1


def test_a_photo_that_fails_the_quality_check_is_not_stored(db, new_scan, no_writes):
    r = client.post(f"/v1/scans/{new_scan['id']}/frames", headers=new_scan["headers"],
                    json={"angle": "front", "image_base64": base64.b64encode(b"definitely not a jpeg").decode()})
    assert r.status_code == 200 and r.json()["passed"] is False
    assert db.query(ScanFrame).filter(ScanFrame.scan_id == new_scan["id"]).one().storage_key == "not-stored"
    assert client.post(f"/v1/scans/{new_scan['id']}/analyze", headers=new_scan["headers"],
                       json={"angle": "front", "image_base64": jpeg_base64()}).status_code == 400


def test_a_failed_analysis_stores_nothing_either(db, new_scan, no_writes, monkeypatch):
    def no_face(frames, part):
        raise ValueError("No face found near the centre of the photo")
    monkeypatch.setattr(scans_endpoint, "analyze_skin_profile", no_face)
    image = jpeg_base64(seed=2)
    client.post(f"/v1/scans/{new_scan['id']}/frames", headers=new_scan["headers"], json={"angle": "front", "image_base64": image})
    r = client.post(f"/v1/scans/{new_scan['id']}/analyze", headers=new_scan["headers"], json={"angle": "front", "image_base64": image})
    assert r.status_code == 422 and "No face" in r.json()["detail"]
    assert db.query(SkinProfile).filter(SkinProfile.scan_id == new_scan["id"]).count() == 0


def test_the_real_analysis_reads_the_photo_from_memory(db, new_scan, no_writes):
    """The unmocked OpenCV/MediaPipe pipeline gets the photo bytes and decodes them in memory. This photo has no
    face, so it is rejected with 422 — after being read, and without anything written."""
    image = jpeg_base64(seed=3)
    client.post(f"/v1/scans/{new_scan['id']}/frames", headers=new_scan["headers"], json={"angle": "front", "image_base64": image})
    r = client.post(f"/v1/scans/{new_scan['id']}/analyze", headers=new_scan["headers"], json={"angle": "front", "image_base64": image})
    assert r.status_code in (422, 503), r.text  # 503 only if the OpenCV runtime itself is unavailable
    if r.status_code == 422:
        assert "Could not read" not in r.json()["detail"]  # the bytes were decoded; the face check said no


def test_the_app_has_no_code_that_stores_photos():
    """The old photo storage (disk / S3) is gone: only the legacy folder's location remains, for the purge script."""
    assert [n for n in dir(storage) if not n.startswith("_") and n != "os"] == ["UPLOAD_DIR"]


def test_validation_failures_failed_analyses_and_retries_leave_no_trace_of_the_photo(db, new_scan, no_writes, monkeypatch, caplog):
    """'Your photo is not stored and is deleted after analysis': on every path — invalid upload, failed quality check,
    failed analysis, retry, success, repeated request — the photo appears in no response, log line, temp file, upload
    folder or database column."""
    import logging
    from sqlalchemy import text
    caplog.set_level(logging.DEBUG)
    image = jpeg_base64(seed=7)
    fragment = image.split(",", 1)[1][1000:1080]  # a piece from inside the photo's data
    frames_url, analyze_url, h = f"/v1/scans/{new_scan['id']}/frames", f"/v1/scans/{new_scan['id']}/analyze", new_scan["headers"]
    responses = []

    # validation failures: not base64 at all, and a request the schema refuses (its 422 must not echo the photo)
    responses.append(client.post(frames_url, headers=h, json={"angle": "front", "image_base64": "%%%" + image}))
    responses.append(client.post(frames_url, headers=h, json={"angle": 7, "image_base64": image}))
    assert responses[-1].status_code == 422
    # a failed quality check, then a failed analysis, then the retry that works
    responses.append(client.post(frames_url, headers=h, json={"angle": "front", "image_base64": base64.b64encode(b"x" * 500).decode()}))
    responses.append(client.post(frames_url, headers=h, json={"angle": "front", "image_base64": image}))
    attempts = []

    def flaky(frames, part):
        attempts.append(len(frames[0]))
        if len(attempts) == 1:
            raise ValueError("No face found near the centre of the photo")
        return METRICS
    monkeypatch.setattr(scans_endpoint, "analyze_skin_profile", flaky)
    responses.append(client.post(analyze_url, headers=h, json={"angle": "front", "image_base64": image}))
    assert responses[-1].status_code == 422
    responses.append(client.post(analyze_url, headers=h, json={"angle": "front", "image_base64": image}))  # retry
    assert responses[-1].status_code == 200, responses[-1].text
    responses.append(client.post(analyze_url, headers=h))  # repeated: the saved result, no photo needed
    assert responses[-1].status_code == 200 and len(attempts) == 2

    for r in responses:
        assert fragment not in r.text, f"photo data echoed by {r.request.url}"
    assert fragment not in caplog.text and "data:image" not in caplog.text
    assert {f.storage_key for f in db.query(ScanFrame).filter(ScanFrame.scan_id == new_scan["id"])} == {"not-stored"}
    columns = db.execute(text("select table_name, column_name from information_schema.columns where table_schema = 'public' "
                              "and data_type in ('text', 'character varying', 'jsonb', 'json')")).all()
    for table, column in columns:
        hit = db.execute(text(f'select count(*) from "{table}" where "{column}"::text like :f'), {"f": f"%{fragment}%"}).scalar()
        assert hit == 0, f"photo data found in {table}.{column}"
