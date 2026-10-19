"""Shared helpers for the report/delivery tests (store snapshot catalogue, stubbed Shopify pricing)."""

from datetime import datetime
from types import SimpleNamespace

QUOTE = {"currency": "INR", "subtotal": 5940.0, "discounts": [{"title": "YWPL1500", "amount": 1500.0}], "total": 4440.0,
         "checkout_url": "https://yuriwoori.com/cart/c/x", "cart_id": "c", "total_quantity": 5, "lines": [], "warnings": []}


def stub_shopify_pricing(monkeypatch):
    from app.services import reports
    sent = []
    monkeypatch.setattr(reports.shopify_cart, "quote", lambda lines: (sent.append(lines), QUOTE)[1])
    return sent


def report_content(monkeypatch, **metrics):
    from app.services import reports
    stub_shopify_pricing(monkeypatch)
    values = dict(skin_type="combination", hydration=38.0, oiliness=30.0, texture=80.0, redness=52.0, pigmentation=44.0,
                  blemish_index=10.0, pore_visibility=48.0, overall_score=64.4)
    values.update(metrics)
    user = SimpleNamespace(id="u", name="Priya")
    scan = SimpleNamespace(id="s", angles_captured=["front"], created_at=datetime(2026, 10, 13, 11, 20))
    return reports.build_content(user, scan, SimpleNamespace(created_at=datetime(2026, 10, 13, 11, 20, 30), **values))
