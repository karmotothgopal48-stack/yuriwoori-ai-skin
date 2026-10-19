"""
Every test reads the store from tests/fixtures/store_snapshot.json (a real capture of yuriwoori.com, made by
scripts/capture_store_snapshot.py) instead of the network. Tests that need a different store patch the two
fetch functions themselves.
"""

import contextlib
import json
import os
import sys
import uuid
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import live_catalogue

SNAPSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "store_snapshot.json")
with open(SNAPSHOT_PATH, encoding="utf-8") as f:
    SNAPSHOT = json.load(f)


@pytest.fixture(autouse=True)
def snapshot_store(monkeypatch):
    live_catalogue.clear_cache()
    monkeypatch.setattr(live_catalogue, "_fetch_raw_products", lambda: SNAPSHOT["products"])
    monkeypatch.setattr(live_catalogue, "_fetch_product_content", lambda handle, client: SNAPSHOT["content"].get(handle))
    monkeypatch.setattr(live_catalogue, "_client", contextlib.nullcontext)  # the stubs never use a real client
    from app.services import report_pdf
    monkeypatch.setattr(report_pdf, "_product_image_png", lambda url: None)  # report PDFs: no image downloads
    yield
    live_catalogue.clear_cache()


@pytest.fixture(autouse=True)
def no_customer_sheet(monkeypatch, tmp_path):
    """Spreadsheet sync off and no service-account key, whatever .env says: no test can reach Google or a real key."""
    from app.core.config import settings
    from app.services import google_sheets
    monkeypatch.setattr(settings, "customer_sheet_sync_enabled", False)
    monkeypatch.setattr(settings, "google_service_account_file", "")
    monkeypatch.setattr(settings, "google_sheets_spreadsheet_id", "")
    monkeypatch.setattr(settings, "ms_graph_token_cache_path", str(tmp_path / "ms_graph_token.json"))  # legacy module
    google_sheets.reset_token()


@pytest.fixture(autouse=True)
def report_after_analysis_on_the_test_database(monkeypatch):
    """The post-analysis report/delivery task runs on the test's own (rolled-back) session, never a new connection."""
    from app.services import delivery
    real = delivery.report_after_analysis

    def run(scan_id, user_id):
        from app.db.session import get_db
        from app.main import app
        override = app.dependency_overrides.get(get_db)
        if override is not None:
            real(scan_id, user_id, db=override())
    monkeypatch.setattr(delivery, "report_after_analysis", run)


@pytest.fixture
def catalogue():
    """The live catalogue built from the snapshot."""
    return live_catalogue.get_catalogue()


# ---------- the real PostgreSQL database (DATABASE_URL), inside a transaction that is always rolled back ----------


def _database_ready() -> bool:
    from sqlalchemy import text
    from app.core.config import settings
    from app.db.session import engine
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1 from products limit 1"))
        return len(settings.jwt_secret) >= 32
    except Exception:
        return False


@pytest.fixture(scope="session")
def database():
    if not _database_ready():
        pytest.skip("PostgreSQL (DATABASE_URL) or JWT_SECRET not available")


@pytest.fixture
def db(database):
    """A session on the real database whose writes are all rolled back; the app uses it too."""
    from sqlalchemy.orm import Session
    from app.db.session import engine, get_db
    from app.main import app
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        transaction.rollback()  # nothing a test wrote is kept
        connection.close()


class SimpleScan:
    def __init__(self, scan_id, profile_id, user_id, headers):
        self.id, self.profile_id, self.user_id, self.headers = scan_id, profile_id, user_id, headers


def make_scan(db, email_prefix="live-catalogue-test", whatsapp="+919876543210", **metrics):
    """A signed-up test user (example.com address) with one analysed face scan, and their session header."""
    from app.core.security import ROLE_USER, create_token
    from app.db.models import Scan, ScanStatus, SkinProfile, User
    user = User(email=f"{email_prefix}-{uuid.uuid4().hex}@example.com", name="Test", whatsapp=whatsapp)
    db.add(user)
    db.flush()
    scan = Scan(user_id=user.id, status=ScanStatus.analyzed, angles_captured=["front"])
    db.add(scan)
    db.flush()
    values = dict(skin_type="dry", hydration=30.0, oiliness=0.0, texture=90.0, redness=10.0, pigmentation=10.0,
                  blemish_index=5.0, pore_visibility=5.0, overall_score=70.0)
    values.update(metrics)
    profile = SkinProfile(scan_id=scan.id, user_id=user.id, **values)
    db.add(profile)
    db.flush()
    token = create_token(str(user.id), ROLE_USER, timedelta(minutes=10))
    return SimpleScan(scan.id, profile.id, user.id, {"Authorization": f"Bearer {token}"})


@pytest.fixture
def dry_scan(db):
    return make_scan(db)
