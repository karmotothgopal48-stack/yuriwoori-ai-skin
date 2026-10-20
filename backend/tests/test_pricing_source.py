"""
Shopify is the only source of product prices. Local records (the products table, the CSV export) and older copies
never decide a price shown or sent; routine, cart, report, PDF and messages all use Shopify's pricing, or say
"Final price unavailable - verify at Shopify checkout." Shopify is stubbed with the stored snapshot (conftest).
"""

import copy
import csv
import os
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.services import catalogue_csv, live_catalogue, report_pdf, reports, shopify_cart
from app.services.delivery import report_messages
from conftest import SNAPSHOT, make_scan
from pdf_text import pdf_text
from tests_support import QUOTE, report_content, stub_shopify_pricing

client = TestClient(app)
FOAM = "rice-facial-deep-cleansing-foam"


def test_a_different_price_in_the_products_table_never_reaches_the_customer(db, catalogue):
    shopify_price = catalogue.by_handle[FOAM].price
    db.execute(text("update products set price = :p where product_url like :u"), {"p": shopify_price + 400, "u": f"%/{FOAM}"})
    db.flush()  # the local record now disagrees with Shopify by ₹400 (rolled back after the test)
    live = client.get(f"/v1/catalogue/live?handles={FOAM}").json()["products"][0]
    assert live["price"] == shopify_price


def test_the_csv_export_is_never_read_to_price_anything(db, monkeypatch, catalogue):
    def forbidden(*args, **kwargs):
        raise AssertionError("the CSV export was read at runtime")
    for name in dir(catalogue_csv):
        if name.startswith(("load", "read", "parse")) and callable(getattr(catalogue_csv, name)):
            monkeypatch.setattr(catalogue_csv, name, forbidden)
    stub_shopify_pricing(monkeypatch)
    scan = make_scan(db, email_prefix="csv-never")
    assert client.get(f"/v1/catalogue/live?handles={FOAM}").status_code == 200
    assert client.get(f"/v1/scans/{scan.id}/routine", headers=scan.headers).status_code == 200
    assert client.post("/v1/reports", headers=scan.headers, json={"scan_id": str(scan.id)}).status_code == 200
    # and its prices may differ from Shopify's: Shopify's are the ones served
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "products_export.csv")
    with open(path, encoding="utf-8-sig") as f:
        assert any(r.get("Handle") == FOAM for r in csv.DictReader(f))


def test_a_price_change_on_shopify_replaces_the_old_one(monkeypatch):
    changed = copy.deepcopy(SNAPSHOT["products"])
    for p in changed:
        if p["handle"] == FOAM:
            p["variants"][0]["price"] = "799.0"
            p["updated_at"] = "2099-01-01T00:00:00+05:30"
    live_catalogue.clear_cache()
    monkeypatch.setattr(live_catalogue, "_fetch_raw_products", lambda: changed)
    assert client.get(f"/v1/catalogue/live?handles={FOAM}").json()["products"][0]["price"] == 799.0


def test_a_shopify_timeout_gives_no_price_rather_than_a_guessed_one(monkeypatch, catalogue):
    def timeout(lines):
        raise httpx.ReadTimeout("Shopify took too long")
    monkeypatch.setattr(shopify_cart, "quote", timeout)
    variant = catalogue.by_handle[FOAM].variant_id
    r = client.post("/v1/shopify/cart", json={"lines": [{"variant_id": variant, "quantity": 1}]})
    assert r.status_code == 502 and "total" not in r.json()


def test_the_report_and_the_routine_cart_price_exactly_the_same_lines_with_shopify(db, monkeypatch, catalogue):
    sent = stub_shopify_pricing(monkeypatch)  # records the lines each Shopify pricing request carries
    scan = make_scan(db, email_prefix="same-lines")
    report = reports.get_or_create(db, db.get(reports.User, scan.user_id), db.get(reports.Scan, scan.id))
    content = reports.content_for(db, report)
    report_lines = sent[-1]
    assert content["pricing"]["subtotal"] == QUOTE["subtotal"] and content["pricing"]["total"] == QUOTE["total"]
    r = client.post("/v1/shopify/cart", json={"lines": report_lines})  # what the routine page / cart send for them
    assert r.status_code == 200
    assert sorted(map(str, sent[-1])) == sorted(map(str, report_lines))  # identical variants and quantities
    assert (r.json()["subtotal"], r.json()["total"]) == (content["pricing"]["subtotal"], content["pricing"]["total"])


def test_without_shopify_pricing_the_pdf_and_messages_say_the_final_price_is_unavailable(monkeypatch):
    content = report_content(monkeypatch)
    content["pricing"] = None  # Shopify couldn't price the routine
    text_ = pdf_text(report_pdf.render(content, "https://skin.yuriwoori.com/report#t=x"))
    assert "Final price unavailable - verify at Shopify checkout." in text_
    assert "Total payable" not in text_
    messages = report_messages(content, "https://skin.yuriwoori.com/report#t=x", None)
    assert "Final price unavailable - verify at Shopify checkout." in messages["text"]


def test_with_shopify_pricing_every_channel_labels_subtotal_discount_and_payable_total(monkeypatch):
    content = report_content(monkeypatch)  # Shopify's (stubbed) answer: 5940 - YWPL1500 1500 = 4440
    text_ = pdf_text(report_pdf.render(content, None))
    for words in ("Subtotal", "Automatic discount YWPL1500", "Shipping and taxes", "Total payable (before shipping)", "Rs. 4,440"):
        assert words in text_, words
    m = report_messages(content, "https://skin.yuriwoori.com/report#t=x", None)["text"]
    assert "subtotal Rs. 5,940" in m and "automatic discount YWPL1500, no code needed -Rs. 1,500" in m and "total payable Rs. 4,440" in m
