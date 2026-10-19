"""
End-to-end against the real PostgreSQL database (DATABASE_URL): scan -> routine / products / compatibility /
click tracking, all from the live catalogue (store snapshot). Everything runs inside one transaction that is
rolled back, so the database is left unchanged. Skipped when the database is not reachable.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.models import Product, Routine
from app.main import app
from app.services import live_catalogue


pytestmark = pytest.mark.usefixtures("database")  # skipped when PostgreSQL isn't reachable (tests/conftest.py)


def test_routine_comes_from_the_live_catalogue_and_follows_it(db, dry_scan, monkeypatch):
    client = TestClient(app)
    r = client.get(f"/v1/scans/{dry_scan.id}/routine", headers=dry_scan.headers)
    assert r.status_code == 200, r.text
    body = r.json()
    catalogue = live_catalogue.get_catalogue()
    steps = body["AM"] + body["PM"]
    assert steps and body["catalogue_fetched_at"] and body["catalogue_stale"] is False
    for step in steps:
        live = catalogue.get(step["handle"])
        assert live and step["price"] == live.price and step["variant_id"] == live.variant_id and step["available"]
        assert step["ingredients"] == list(live.ingredients) and step["benefits"] and step["how_to_use"] == live.how_to_use
        row = db.get(Product, uuid.UUID(step["product_id"]))
        assert row.shopify_product_id == live.handle and row.shopify_variant_id == live.variant_gid
    assert db.query(Routine).filter(Routine.skin_profile_id == dry_scan.profile_id).count() == 1

    # asking again with the same live data: same routine, no new version
    assert client.get(f"/v1/scans/{dry_scan.id}/routine", headers=dry_scan.headers).json()["AM"] == body["AM"]
    assert db.query(Routine).filter(Routine.skin_profile_id == dry_scan.profile_id).count() == 1

    # ingredient notes use the saved (latest) routine
    assert client.get(f"/v1/scans/{dry_scan.id}/compatibility", headers=dry_scan.headers).status_code == 200

    # the store stops selling the morning cleanser: the next request rebuilds without it, as a new version
    gone = body["AM"][0]["handle"]
    feed = [p for p in live_catalogue._fetch_raw_products() if p["handle"] != gone]
    monkeypatch.setattr(live_catalogue, "_fetch_raw_products", lambda: feed)
    live_catalogue.clear_cache()
    changed = client.get(f"/v1/scans/{dry_scan.id}/routine", headers=dry_scan.headers).json()
    assert gone not in {s["handle"] for s in changed["AM"] + changed["PM"]}
    assert db.query(Routine).filter(Routine.skin_profile_id == dry_scan.profile_id).count() == 2

    # a product page click is accepted for a product the scan was offered
    clicked = changed["AM"][0]["handle"]
    r = client.post("/v1/events", headers=dry_scan.headers,
                    json={"event_type": "product_clicked", "scan_id": str(dry_scan.id), "product_handle": clicked})
    assert r.status_code == 200, r.text


def test_products_endpoint_lists_live_products_with_stable_ids(db):
    client = TestClient(app)
    listed = client.get("/v1/products").json()
    catalogue = live_catalogue.get_catalogue()
    assert {p["handle"] for p in listed} == set(catalogue.by_handle)
    toner = next(p for p in listed if p["handle"] == "bubble-soothing-toner")
    assert toner["price"] == catalogue.get("bubble-soothing-toner").price
    detail = client.get(f"/v1/products/{toner['id']}").json()
    assert detail["ingredients"] and detail["benefits"]
    assert client.get("/v1/products").json()[0]["id"] == listed[0]["id"]  # same row, not a new one


def test_routine_is_503_not_stale_data_when_the_store_is_unavailable(db, dry_scan, monkeypatch):
    def down():
        raise live_catalogue.httpx.ConnectError("store down")
    monkeypatch.setattr(live_catalogue, "_fetch_raw_products", down)
    r = TestClient(app).get(f"/v1/scans/{dry_scan.id}/routine", headers=dry_scan.headers)
    assert r.status_code == 503
