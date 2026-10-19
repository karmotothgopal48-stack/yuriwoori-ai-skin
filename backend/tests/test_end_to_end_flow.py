"""
The whole customer journey through the API, on the real database (rolled back; skipped without PostgreSQL):
signup with consent -> mobile (WhatsApp) code -> scan -> photo quality check -> REAL skin analysis of a real
face photo (the brand's campaign portrait; nothing stubbed) -> concerns, recommendations and AM/PM routine from
the store catalogue (tests read the captured store snapshot) -> report -> automatic delivery to the customer's
own email and verified WhatsApp number (providers replaced by an outbox; Shopify pricing stubbed).
Throughout, any attempt to write the photo fails the test, and nothing image-like may end up in the database.
"""

import base64
import json
import os
import tempfile
import uuid

import cv2
import pytest
from fastapi.testclient import TestClient

from app.db.models import Report, ScanFrame
from app.main import app
from app.services import storage
from test_delivery_db import code_from, outbox  # noqa: F401  (outbox is a fixture)
from test_no_selfie_storage import files_under

client = TestClient(app)
PORTRAIT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "assets", "permission-portrait.webp")
pytestmark = pytest.mark.skipif(not os.path.exists(PORTRAIT), reason="frontend campaign portrait not available")


def portrait_jpeg() -> str:
    ok, data = cv2.imencode(".jpg", cv2.imread(PORTRAIT), [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return "data:image/jpeg;base64," + base64.b64encode(data.tobytes()).decode()


@pytest.fixture
def photo_never_written(monkeypatch):
    image = portrait_jpeg()  # encoded before the traps are set

    def forbidden(*args, **kwargs):
        raise AssertionError("a scan photo was about to be written")
    monkeypatch.setattr(cv2, "imwrite", forbidden)
    for name in ("mkstemp", "NamedTemporaryFile", "TemporaryFile", "SpooledTemporaryFile"):
        monkeypatch.setattr(tempfile, name, forbidden)
    before = files_under(storage.UPLOAD_DIR)
    yield image
    assert files_under(storage.UPLOAD_DIR) == before, "files were added to the upload folder"


def test_signup_to_delivered_report_with_a_real_analysis(db, outbox, photo_never_written):  # noqa: F811
    image = photo_never_written
    email, number = f"journey-{uuid.uuid4().hex}@example.com", "+447700900321"

    # 1. details + privacy consent + consent to have the report sent
    r = client.post("/v1/users/signup", json={"name": "Asha", "whatsapp": "07700 900321".replace("0", "+44", 1),
                                               "email": email, "consent": True, "report_consent": True})
    assert r.status_code == 200, r.text
    user, headers = r.json()["user"], {"Authorization": f"Bearer {r.json()['token']}"}
    assert user["whatsapp"] == number and not user["whatsapp_verified"] and not user["email_verified"]

    # 2. the mobile code step (a wrong code is refused; nothing is verified by it)
    status = client.get("/v1/delivery/status", headers=headers).json()
    assert status["whatsapp"]["available"] and not status["whatsapp"]["verified"]
    assert client.post("/v1/delivery/verify/start", headers=headers, json={"channel": "whatsapp"}).status_code == 200
    code = code_from(outbox)
    assert outbox[-1]["to"] == number  # the code went to the number the customer entered
    wrong = "000000" if code != "000000" else "111111"
    assert client.post("/v1/delivery/verify/confirm", headers=headers, json={"channel": "whatsapp", "code": wrong}).status_code == 400
    r = client.post("/v1/delivery/verify/confirm", headers=headers, json={"channel": "whatsapp", "code": code})
    assert r.status_code == 200 and r.json()["deliveries"] == []  # no report yet

    # 3. scan + quality check of the photo
    scan_id = client.post("/v1/scans", headers=headers).json()["scan_id"]
    frame = client.post(f"/v1/scans/{scan_id}/frames", headers=headers, json={"angle": "front", "image_base64": image})
    assert frame.status_code == 200 and frame.json()["passed"], frame.text

    # 4. the real analysis (face found, measured in memory); the backend then makes and sends the report by itself
    before = len(outbox)
    r = client.post(f"/v1/scans/{scan_id}/analyze", headers=headers, json={"angle": "front", "image_base64": image})
    assert r.status_code == 200, r.text
    profile = r.json()
    assert profile["skin_type"] and profile["model_version"] == "heuristic-cv-v0"
    for key in ("hydration", "oiliness", "texture", "redness", "pigmentation", "blemish_index", "pore_visibility", "overall_score"):
        assert 0 <= profile[key] <= 100, key

    # 5. concerns + recommendations + AM/PM routine from the store catalogue, with prices
    recs = client.get(f"/v1/catalogue/recommendations?scan_id={scan_id}", headers=headers)
    assert recs.status_code == 200 and recs.json()["analysis_status"] in ("balanced", "concerns"), recs.text
    routine = client.get(f"/v1/scans/{scan_id}/routine", headers=headers).json()
    steps = routine["AM"] + routine["PM"]
    assert routine["AM"] and routine["PM"]
    assert all(s["product_url"].startswith("https://") and s["price"] and s["price"] > 0 for s in steps)

    # 6. the report went out automatically after the analysis (no browser request needed), to this customer's own
    #    contacts, once; the browser's own request afterwards finds it sent and sends nothing again
    sent = outbox[before:]
    r = client.post("/v1/reports", headers=headers, json={"scan_id": scan_id})
    assert r.status_code == 200, r.text
    assert {d["channel"]: d["status"] for d in r.json()["deliveries"]} == {"email": "sent", "whatsapp": "accepted"}
    assert {m["channel"]: m["to"] for m in sent} == {"email": email, "whatsapp": number}
    mail = next(m for m in sent if m["channel"] == "email")
    assert mail["attachments"][0][1].startswith(b"%PDF-") and "Hi Asha," in mail["text"]
    assert client.post("/v1/reports", headers=headers, json={"scan_id": scan_id}).status_code == 200
    assert len(outbox) == before + 2  # asking again sends nothing twice
    assert client.get("/v1/users/me", headers=headers).json()["email_verified"] is False  # not labelled verified

    # 7. no photo anywhere: the frame keeps only scores; the report holds no image data
    frames = db.query(ScanFrame).filter(ScanFrame.scan_id == scan_id).all()
    assert frames and all(f.storage_key == "not-stored" for f in frames)
    saved = json.dumps(db.query(Report).filter(Report.scan_id == scan_id).one().content)
    assert image.split(",", 1)[1][:200] not in saved and "base64" not in saved and "data:image" not in saved

    # 8. nobody else can read or send it
    other = client.post("/v1/users/signup", json={"name": "B", "whatsapp": "+447700900322", "email": f"x-{uuid.uuid4().hex}@example.com",
                                                   "consent": True}).json()
    other_headers = {"Authorization": f"Bearer {other['token']}"}
    assert client.get(f"/v1/reports/scan/{scan_id}", headers=other_headers).status_code == 403
    assert client.post(f"/v1/delivery/scans/{scan_id}/send", headers=other_headers, json={"channel": "email"}).status_code == 403
    assert client.get(f"/v1/scans/{scan_id}", headers=other_headers).status_code == 403

    # 9. the report itself was never stored, and the Google Sheet: this customer qualifies (current notice + verified
    #    WhatsApp), so they are queued in PostgreSQL; with sync off nothing is written to Google
    from app.db.models import CustomerSheetSync, User as UserRow
    from app.services import customer_sheet
    assert db.query(Report).filter(Report.scan_id == scan_id).one().content is None
    me = db.get(UserRow, uuid.UUID(user["id"]))
    assert me.consent_version == "2026-10-19c" and me.whatsapp_verified_at is not None and customer_sheet.eligible(me)
    job = db.get(CustomerSheetSync, me.id)
    assert job is not None and job.status == "pending" and customer_sheet.process_due(db) == {"skipped": "disabled"}
    assert db.get(CustomerSheetSync, uuid.UUID(other["user"]["id"])) is None  # signed up, never verified: not queued
