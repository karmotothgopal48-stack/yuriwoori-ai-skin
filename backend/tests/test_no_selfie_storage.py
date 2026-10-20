"""
No selfie storage: scan photos are checked and analysed in memory, never written to disk, the database or S3.
Runs the real scan endpoints on the real database (rolled back; skipped without PostgreSQL). The `no_writes` guards
watch every route a photo could leave memory by and record a violation when image data reaches one:
  * ordinary file writes: open() / io.open (pathlib's write_bytes / write_text use it) and os.write;
  * image and temp-file APIs: cv2.imwrite, PIL Image.save, every tempfile creator (all refused outright);
  * cloud storage: boto3 clients, resources and sessions (refused outright);
  * outbound HTTP: httpx requests to anything but the app under test (the test client's own host);
  * the database: every SQL statement's parameters;
  * logs: everything logged, at DEBUG.
"Image data" = the test photo's own fragments (raw and base64) plus generic signatures (JPEG/PNG/WebP bytes, base64
JPEG/PNG headers, data:image URLs). The positive controls at the end prove each guard fires. These tests show the
guarded routes stay clean on the paths exercised; they can't prove that no other route exists.
"""

import base64
import builtins
import io
import logging
import os
import tempfile

import boto3
import cv2
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError

from app.api.v1.endpoints import scans as scans_endpoint
from app.db.models import ScanFrame, SkinProfile
from app.db.session import engine
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


IMAGE_BYTES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")  # JPEG / PNG file signatures (WebP: RIFF....WEBP, below)
IMAGE_TEXT = ("data:image/", ";base64,", "/9j/4", "iVBORw0KGgo")  # data URLs, base64 JPEG / PNG headers


class PhotoGuard:
    """Records every attempt to send image data somewhere it could be kept (see the module docstring)."""

    def __init__(self):
        self.violations, self.text_needles, self.byte_needles = [], list(IMAGE_TEXT), list(IMAGE_BYTES)

    def watch(self, image_base64: str):
        """Also look for fragments from inside this photo (raw bytes and base64), not only its headers."""
        b64 = image_base64.split(",", 1)[-1]
        raw = base64.b64decode(b64)
        self.text_needles += [b64[len(b64) // 3:][:64], b64[len(b64) // 2:][:64]]
        self.byte_needles += [raw[len(raw) // 3:][:48], raw[len(raw) // 2:][:48]]
        return image_base64

    def has_image(self, data) -> bool:
        if isinstance(data, (bytes, bytearray, memoryview)):
            data = bytes(data)
            return (any(n in data for n in self.byte_needles) or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
                    or any(n.encode() in data for n in self.text_needles))
        if isinstance(data, str):
            return any(n in data for n in self.text_needles)
        if isinstance(data, dict):
            return any(self.has_image(v) for v in data.values())
        if isinstance(data, (list, tuple, set)):
            return any(self.has_image(v) for v in data)
        return False

    def flag(self, where: str):
        self.violations.append(where)
        raise AssertionError(f"image data reached {where}")


class _GuardedFile:
    """A file opened for writing: every write is checked before it reaches the real file."""

    def __init__(self, f, guard, name):
        self._f, self._guard, self._name = f, guard, name

    def write(self, data):
        if self._guard.has_image(data):
            self._guard.flag(f"open({self._name!r}).write()")
        return self._f.write(data)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def __enter__(self):
        self._f.__enter__()
        return self

    def __exit__(self, *exc):
        return self._f.__exit__(*exc)

    def __iter__(self):
        return iter(self._f)

    def __getattr__(self, name):
        return getattr(self._f, name)


@pytest.fixture
def no_writes(monkeypatch):
    """Every route a photo could leave memory by is guarded (module docstring). Afterwards: no violations, and the
    legacy upload folder is unchanged. Returns the guard, so a test can watch its own photo's fragments."""
    guard = PhotoGuard()

    def refused(what):
        def call(*args, **kwargs):
            guard.flag(what)
        return call

    real_open = builtins.open

    def guarded_open(file, mode="r", *args, **kwargs):
        f = real_open(file, mode, *args, **kwargs)
        return _GuardedFile(f, guard, str(file)) if any(m in mode for m in "wax+") else f
    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)  # pathlib's write_bytes / write_text open files through io.open

    real_os_write = os.write

    def guarded_os_write(fd, data):
        if guard.has_image(data):
            guard.flag(f"os.write(fd {fd})")
        return real_os_write(fd, data)
    monkeypatch.setattr(os, "write", guarded_os_write)

    monkeypatch.setattr(cv2, "imwrite", refused("cv2.imwrite"))
    monkeypatch.setattr(PILImage.Image, "save", refused("PIL Image.save"))
    for name in ("mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryFile", "SpooledTemporaryFile", "TemporaryDirectory"):
        monkeypatch.setattr(tempfile, name, refused(f"tempfile.{name}"))
    for name in ("client", "resource", "Session"):
        monkeypatch.setattr(boto3, name, refused(f"boto3.{name} (cloud storage)"))
    monkeypatch.setattr(boto3.session, "Session", refused("boto3.session.Session (cloud storage)"))

    real_send = httpx.Client.send

    def guarded_send(self, request, *args, **kwargs):
        # the test client's own requests to the app carry the photo by design; any other host must never get it
        if request.url.host != "testserver" and guard.has_image(request.content):
            guard.flag(f"HTTP {request.method} {request.url.host}")
        return real_send(self, request, *args, **kwargs)
    monkeypatch.setattr(httpx.Client, "send", guarded_send)

    def guarded_sql(conn, cursor, statement, parameters, context, executemany):
        if guard.has_image(parameters) or (parameters and _has_binary(parameters)):
            guard.flag(f"SQL: {statement.split()[0]} …")
    event.listen(engine, "before_cursor_execute", guarded_sql)

    logs = io.StringIO()
    handler = logging.StreamHandler(logs)
    root = logging.getLogger()
    root.addHandler(handler)
    level = root.level
    root.setLevel(logging.DEBUG)

    before = files_under(storage.UPLOAD_DIR)
    try:
        yield guard
    finally:
        event.remove(engine, "before_cursor_execute", guarded_sql)
        root.removeHandler(handler)
        root.setLevel(level)
    assert not guard.violations, f"image data reached: {guard.violations}"
    assert not guard.has_image(logs.getvalue()), "image data was logged"
    assert files_under(storage.UPLOAD_DIR) == before, "files were added to the upload folder"


def _has_binary(parameters) -> bool:
    if isinstance(parameters, (bytes, bytearray, memoryview)):
        return True
    if isinstance(parameters, dict):
        return any(_has_binary(v) for v in parameters.values())
    if isinstance(parameters, (list, tuple)):
        return any(_has_binary(v) for v in parameters)
    return False


def assert_photo_kept_nowhere(db, scan_id, image, responses=()):
    """After a scan: its frames say 'not-stored', no response echoes the photo, and no text/JSON column holds it."""
    fragment = image.split(",", 1)[1][1000:1080]
    for r in responses:
        assert fragment not in r.text and "data:image" not in r.text, f"photo data echoed by {r.request.url}"
    assert {f.storage_key for f in db.query(ScanFrame).filter(ScanFrame.scan_id == scan_id)} <= {"not-stored"}
    columns = db.execute(text("select table_name, column_name from information_schema.columns where table_schema = 'public' "
                              "and data_type in ('text', 'character varying', 'jsonb', 'json', 'ARRAY')")).all()
    for table, column in columns:
        hit = db.execute(text(f'select count(*) from "{table}" where "{column}"::text like :f'), {"f": f"%{fragment}%"}).scalar()
        assert hit == 0, f"photo data found in {table}.{column}"


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


# ---------- every path a scan can take, with all guards on ----------

PORTRAIT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "assets", "permission-portrait.webp")


def portrait_base64() -> str:
    """The brand's own campaign portrait (a real face, never a customer's photo), as the app sends a capture."""
    ok, data = cv2.imencode(".jpg", cv2.imread(PORTRAIT), [cv2.IMWRITE_JPEG_QUALITY, 92])
    return "data:image/jpeg;base64," + base64.b64encode(data.tobytes()).decode()


def send(scan, image, analyze_image=None):
    """Upload the photo for the quality check, then send it again for the analysis (the app's two steps)."""
    h = scan["headers"]
    frame = client.post(f"/v1/scans/{scan['id']}/frames", headers=h, json={"angle": "front", "image_base64": image})
    analysis = client.post(f"/v1/scans/{scan['id']}/analyze", headers=h,
                           json={"angle": "front", "image_base64": analyze_image if analyze_image is not None else image})
    return frame, analysis


@pytest.mark.skipif(not os.path.exists(PORTRAIT), reason="frontend campaign portrait not available")
def test_a_real_face_is_analysed_end_to_end_without_storing_it(db, new_scan, no_writes):
    """Success on the unmocked MediaPipe + OpenCV pipeline, with every guard on."""
    image = no_writes.watch(portrait_base64())
    frame, analysis = send(new_scan, image)
    assert frame.status_code == 200 and frame.json()["passed"] is True, frame.text
    assert analysis.status_code == 200 and analysis.json()["overall_score"] is not None, analysis.text
    assert db.query(SkinProfile).filter(SkinProfile.scan_id == new_scan["id"]).count() == 1  # results are kept
    assert_photo_kept_nowhere(db, new_scan["id"], image, [frame, analysis])


def test_invalid_image_data_at_analysis_is_refused_and_not_kept(db, new_scan, no_writes):
    image = no_writes.watch(jpeg_base64(seed=11))
    frame, analysis = send(new_scan, image, analyze_image="%%%not-base64%%%")
    assert frame.status_code == 200 and analysis.status_code == 400
    assert_photo_kept_nowhere(db, new_scan["id"], image, [frame, analysis])


def test_an_exception_inside_image_processing_keeps_nothing(db, new_scan, no_writes, monkeypatch):
    def crash(frames, part):
        raise RuntimeError("simulated crash inside image processing")
    monkeypatch.setattr(scans_endpoint, "analyze_skin_profile", crash)
    image = no_writes.watch(jpeg_base64(seed=12))
    frame, analysis = send(new_scan, image)
    assert analysis.status_code == 500 and "simulated" not in analysis.text  # generic message, nothing echoed
    assert db.query(SkinProfile).filter(SkinProfile.scan_id == new_scan["id"]).count() == 0
    assert_photo_kept_nowhere(db, new_scan["id"], image, [frame, analysis])


def test_a_database_failure_during_the_analysis_keeps_nothing(db, new_scan, no_writes, monkeypatch):
    monkeypatch.setattr(scans_endpoint, "analyze_skin_profile", lambda frames, part: METRICS)
    image = no_writes.watch(jpeg_base64(seed=13))
    frame = client.post(f"/v1/scans/{new_scan['id']}/frames", headers=new_scan["headers"], json={"angle": "front", "image_base64": image})
    real_commit = db.commit

    def outage():
        raise OperationalError("COMMIT", {}, Exception("simulated database outage"))
    db.commit = outage
    try:
        analysis = client.post(f"/v1/scans/{new_scan['id']}/analyze", headers=new_scan["headers"], json={"angle": "front", "image_base64": image})
    finally:
        db.commit = real_commit
    assert analysis.status_code == 503
    assert_photo_kept_nowhere(db, new_scan["id"], image, [frame, analysis])


class SimulatedInterruption(BaseException):
    """Stands in for a request abandoned mid-analysis: a BaseException, so no error handler turns it into a response."""


def test_an_analysis_interrupted_midway_keeps_nothing(db, new_scan, no_writes, monkeypatch):
    """Simulated cancellation (a real client disconnect can't be reproduced with the test client)."""
    def interrupted(frames, part):
        raise SimulatedInterruption()
    monkeypatch.setattr(scans_endpoint, "analyze_skin_profile", interrupted)
    image = no_writes.watch(jpeg_base64(seed=14))
    frame = client.post(f"/v1/scans/{new_scan['id']}/frames", headers=new_scan["headers"], json={"angle": "front", "image_base64": image})
    with pytest.raises(SimulatedInterruption):
        client.post(f"/v1/scans/{new_scan['id']}/analyze", headers=new_scan["headers"], json={"angle": "front", "image_base64": image})
    assert db.query(SkinProfile).filter(SkinProfile.scan_id == new_scan["id"]).count() == 0
    assert_photo_kept_nowhere(db, new_scan["id"], image, [frame])


def test_a_restart_after_a_failure_and_a_duplicate_request_keep_nothing(db, new_scan, no_writes, monkeypatch):
    calls = []

    def first_fails(frames, part):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("No face found near the centre of the photo")
        return METRICS
    monkeypatch.setattr(scans_endpoint, "analyze_skin_profile", first_fails)
    first = no_writes.watch(jpeg_base64(seed=15))
    responses = list(send(new_scan, first))
    assert responses[-1].status_code == 422
    # the customer restarts: a new scan with a new photo, then sends the same analysis twice (double tap / retry)
    restart = {"id": client.post("/v1/scans", headers=new_scan["headers"]).json()["scan_id"], "headers": new_scan["headers"]}
    second = no_writes.watch(jpeg_base64(seed=16))
    responses += send(restart, second)
    responses.append(client.post(f"/v1/scans/{restart['id']}/analyze", headers=restart["headers"], json={"angle": "front", "image_base64": second}))
    assert [r.status_code for r in responses[-2:]] == [200, 200] and len(calls) == 2  # the duplicate reuses the saved result
    assert db.query(SkinProfile).filter(SkinProfile.scan_id == restart["id"]).count() == 1
    for scan_id, image in ((new_scan["id"], first), (restart["id"], second)):
        assert_photo_kept_nowhere(db, scan_id, image, responses)


# ---------- the guards themselves: each must fire (positive controls) and stay out of the way otherwise ----------

def test_every_guard_fires_when_image_data_reaches_it(no_writes, tmp_path):
    image = no_writes.watch(jpeg_base64(seed=21))
    raw = base64.b64decode(image.split(",", 1)[1])
    attempts = {
        "open() binary write": lambda: open(tmp_path / "a.jpg", "wb").write(raw),
        "open() text write of base64": lambda: open(tmp_path / "a.txt", "w").write(image),
        "open() append": lambda: open(tmp_path / "b.txt", "a").write(image.split(",", 1)[1]),
        "pathlib write_bytes": lambda: (tmp_path / "c.jpg").write_bytes(raw),
        "pathlib write_text": lambda: (tmp_path / "c.txt").write_text(image),
        "os.write": lambda: os.write(os.open(tmp_path / "d.bin", os.O_WRONLY | os.O_CREAT), raw),
        "cv2.imwrite": lambda: cv2.imwrite(str(tmp_path / "e.jpg"), np.zeros((4, 4, 3), np.uint8)),
        "PIL Image.save": lambda: PILImage.new("RGB", (4, 4)).save(tmp_path / "f.png"),
        "tempfile.mkdtemp": lambda: tempfile.mkdtemp(),
        "tempfile.NamedTemporaryFile": lambda: tempfile.NamedTemporaryFile(),
        "boto3.client (S3)": lambda: boto3.client("s3"),
        "outbound HTTP": lambda: httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))).post("https://example.com/upload", content=raw),
    }
    for name, attempt in attempts.items():
        with pytest.raises(AssertionError, match="image data reached"):
            attempt()
        assert no_writes.violations, f"{name}: not recorded"
        no_writes.violations.clear()
    for name, params in {"SQL text parameter": {"p": image}, "SQL binary parameter": {"p": b"\x00\x01binary"}}.items():
        with engine.connect() as conn, pytest.raises(AssertionError, match="image data reached"):
            conn.execute(text("select :p"), params)
        assert no_writes.violations, f"{name}: not recorded"
        no_writes.violations.clear()
    assert no_writes.has_image(f"log line … {image[:40]}") and no_writes.has_image(raw[:3])  # what the log check looks for


@pytest.mark.parametrize("leak", ["file", "database", "log"])
def test_the_guards_also_catch_a_leak_inside_a_request(db, new_scan, no_writes, monkeypatch, tmp_path, leak):
    """Positive control on the real request path: a deliberately leaky analysis (photo bytes to a file, into the
    database, or into the log) is caught, even though the app's error handler turns exceptions into a 500."""
    def leaky(frames, part):
        if leak == "file":
            open(tmp_path / "leak.jpg", "wb").write(frames[0])
        elif leak == "database":
            db.execute(text("select :p"), {"p": base64.b64encode(frames[0]).decode()})
        else:
            logging.getLogger("yuriwoori").info("analysing %s", base64.b64encode(frames[0]).decode()[:200])
        return METRICS
    monkeypatch.setattr(scans_endpoint, "analyze_skin_profile", leaky)
    image = no_writes.watch(jpeg_base64(seed=31))
    send(new_scan, image)
    if leak == "log":  # the log guard runs at teardown: apply the same check here, then empty the captured log
        captured = [h.stream for h in logging.getLogger().handlers if isinstance(getattr(h, "stream", None), io.StringIO)]
        assert any(no_writes.has_image(s.getvalue()) for s in captured), "leak into the log not detected"
        for s in captured:
            s.seek(0)
            s.truncate()
    else:
        assert no_writes.violations, f"leak into the {leak} not detected"
        no_writes.violations.clear()


def test_the_guards_leave_ordinary_work_alone(no_writes, tmp_path, db):
    """No over-blocking: normal file writes, SQL and test-client requests still work."""
    with open(tmp_path / "notes.txt", "w") as f:
        f.write("hello, not an image")
    assert (tmp_path / "notes.txt").read_text() == "hello, not an image"
    (tmp_path / "data.bin").write_bytes(b"\x00\x01plain bytes")
    assert db.execute(text("select :p"), {"p": "plain text"}).scalar() == "plain text"
    assert client.get("/v1/health").status_code == 200
    assert not no_writes.violations
