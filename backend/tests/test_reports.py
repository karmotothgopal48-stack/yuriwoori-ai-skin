"""
Report content and PDF (app/services/reports.py, report_pdf.py), offline: the store is the snapshot fixture,
Shopify's cart pricing is stubbed with the real YWPL1500 response shape, and no images are downloaded.
"""

from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest

from app.services import report_pdf, reports
from app.services.shopify_client import ShopifyError
from pdf_text import pdf_text

QUOTE = {"currency": "INR", "subtotal": 5940.0, "discounts": [{"title": "YWPL1500", "amount": 1500.0}], "total": 4440.0,
         "checkout_url": "https://yuriwoori.com/cart/c/x", "cart_id": "c", "total_quantity": 5, "lines": [], "warnings": []}


@pytest.fixture
def shopify_prices(monkeypatch):
    sent = []
    monkeypatch.setattr(reports.shopify_cart, "quote", lambda lines: (sent.append(lines), QUOTE)[1])
    return sent


def subject(**metrics):
    values = dict(skin_type="combination", hydration=38.0, oiliness=30.0, texture=80.0, redness=52.0, pigmentation=44.0,
                  blemish_index=10.0, pore_visibility=48.0, overall_score=64.4)
    values.update(metrics)
    user = SimpleNamespace(id="u", name="Priya", email="priya@example.com", whatsapp="+919876543210")
    scan = SimpleNamespace(id="s", angles_captured=["front"], created_at=datetime(2026, 10, 13, 11, 20))
    profile = SimpleNamespace(created_at=datetime(2026, 10, 13, 11, 20, 30), **values)
    return user, scan, profile


def test_report_uses_only_the_saved_measurements(shopify_prices):
    content = reports.build_content(*subject())
    assert {m["key"]: m["value"] for m in content["metrics"]} == {
        "hydration": 38, "oiliness": 30, "texture": 80, "redness": 52, "pigmentation": 44, "pore_visibility": 48, "blemish_index": 10}
    assert content["overall_score"] == 64 and content["skin_type"] == "Combination" and content["customer_name"] == "Priya"
    redness = next(m for m in content["metrics"] if m["key"] == "redness")
    assert redness["concern"] == "calm visible redness" and redness["benchmark"] == 15
    assert redness["measures"] == "The average red tone of the skin-coloured pixels in the measured skin area."  # the app's own wording
    # brightening and uneven-tone share one phrase: listed once
    assert [c["phrase"] for c in content["concerns"]].count("even out uneven tone") == 1
    assert content["analysis_date"] == "2026-10-13T11:20:30Z"


def test_routine_and_products_come_from_the_live_catalogue(shopify_prices, catalogue):
    content = reports.build_content(*subject())
    steps = content["routine"]["AM"] + content["routine"]["PM"]
    assert content["routine"]["AM"] and content["routine"]["PM"]
    for step in steps:
        p, live = content["products"][step["handle"]], catalogue.get(step["handle"])
        assert (p["name"], p["variant_id"], p["price"], p["compare_at_price"], p["image_url"], p["url"]) == \
               (live.name, live.variant_id, live.price, live.compare_at_price, live.image_url, live.product_url)
        assert p["available"] and p["how_to_use"] == live.how_to_use
    assert all(x["handle"] not in {s["handle"] for s in steps} for x in content["extras"])


def test_totals_and_discounts_are_shopifys_for_the_routine(shopify_prices):
    content = reports.build_content(*subject())
    routine_variants = list(dict.fromkeys(content["products"][s["handle"]]["variant_id"]
                                          for p in ("AM", "PM") for s in content["routine"][p]))
    assert shopify_prices[0] == [{"variant_id": v, "quantity": 1} for v in routine_variants]
    assert content["pricing"]["subtotal"] == 5940.0 and content["pricing"]["discounts"] == [{"title": "YWPL1500", "amount": 1500.0}]
    assert content["pricing"]["total"] == 4440.0 and content["pricing"]["variant_ids"] == routine_variants


@pytest.mark.parametrize("failure", [ShopifyError("cart refused"), httpx.ConnectError("down")])
def test_without_shopify_pricing_no_total_is_invented(monkeypatch, failure):
    def down(lines):
        raise failure
    monkeypatch.setattr(reports.shopify_cart, "quote", down)
    assert reports.build_content(*subject())["pricing"] is None


def test_balanced_scan_gets_a_maintenance_routine_and_no_concerns(shopify_prices):
    content = reports.build_content(*subject(hydration=84.0, redness=11.0, pigmentation=20.0, pore_visibility=3.0))
    assert content["analysis_status"] == "balanced" and content["concerns"] == [] and content["extras"] == []
    assert [s["step"] for s in content["routine"]["AM"]] == ["cleanse", "tone", "moisturize", "protect"]


def test_hand_scan_reports_only_what_a_hand_scan_measures(shopify_prices):
    user, scan, profile = subject(oiliness=None, pore_visibility=None, blemish_index=None, hydration=20.0)
    scan.angles_captured = ["hand"]
    content = reports.build_content(user, scan, profile)
    assert {m["key"] for m in content["metrics"]} == {"hydration", "texture", "redness", "pigmentation"}
    assert content["benchmark_note"] is None and all(m["benchmark"] is None for m in content["metrics"])
    assert all(content["products"][s["handle"]]["routine_step"] == "moisturize" for s in content["routine"]["AM"])


def test_an_incomplete_analysis_gets_no_report(shopify_prices):
    with pytest.raises(reports.ReportUnavailable):
        reports.build_content(*subject(redness=None))


def test_report_links_are_unguessable_and_stored_only_as_a_hash(monkeypatch):
    monkeypatch.setattr(reports.settings, "jwt_secret", "s" * 40)
    monkeypatch.setattr(reports.settings, "frontend_public_url", "https://skin.yuriwoori.com/")
    token = reports.link_token("6f1c0b9e-0000-4000-8000-000000000001")
    assert token == reports.link_token("6f1c0b9e-0000-4000-8000-000000000001") and len(token) == 43  # 256 bits
    assert token != reports.link_token("6f1c0b9e-0000-4000-8000-000000000002")
    assert reports.token_hash(token) != token and len(reports.token_hash(token)) == 64
    report = SimpleNamespace(id="6f1c0b9e-0000-4000-8000-000000000001")
    assert reports.report_url(report) == f"https://skin.yuriwoori.com/report#t={token}"  # fragment: never sent to servers


def test_pdf_has_every_section_and_no_contact_details(shopify_prices):
    content = reports.build_content(*subject())
    pdf = report_pdf.render(content, "https://skin.yuriwoori.com/report#t=abc")
    assert pdf.startswith(b"%PDF-")
    text = pdf_text(pdf)
    for needle in ("YuriWoori Skin Analysis Report", "Priya", "13 Oct 2026", "Your measurements", "Redness", "Flagged: calm visible redness",
                   "What we noticed", "Morning routine", "Evening routine", "How to use:", "Automatic discount", "YWPL1500", "no code needed", "Rs. 4,440",
                   "continue to checkout", "report#t=abc", "not a medical diagnosis", "internal YuriWoori benchmarks"):
        assert needle in text, needle
    assert "priya@example.com" not in text and "9876543210" not in text


def test_pdf_states_when_shopify_could_not_price_the_routine(monkeypatch):
    monkeypatch.setattr(reports.shopify_cart, "quote", lambda lines: (_ for _ in ()).throw(ShopifyError("x")))
    text = pdf_text(report_pdf.render(reports.build_content(*subject())))
    assert "couldn't price the routine" in text and "Rs. 4,440" not in text


def test_pdf_embeds_product_images_when_they_load(shopify_prices):
    import io
    import zlib
    from PIL import Image

    def distinct_image(url):  # ReportLab stores identical images once, so give each product its own
        png = io.BytesIO()
        h = zlib.crc32(url.encode())
        Image.new("RGB", (40, 40), (h & 255, (h >> 8) & 255, (h >> 16) & 255)).save(png, format="PNG")
        return png.getvalue()

    content = reports.build_content(*subject())
    shown = {s["handle"] for p in ("AM", "PM") for s in content["routine"][p]} | {x["handle"] for x in content["extras"]}
    pdf = report_pdf.render(content, image_loader=distinct_image)
    assert pdf.count(b"/Subtype /Image") == len({content["products"][h]["image_url"] for h in shown})
