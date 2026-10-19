"""
Saves a snapshot of the live YuriWoori store (Storefront API products + each product page's copy) to
tests/fixtures/store_snapshot.json. The tests read the catalogue from this file instead of the network,
so they run offline against real store data. Re-run to refresh it:

    python scripts/capture_store_snapshot.py
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.getcwd())

from app.services import live_catalogue

OUT = os.path.join("tests", "fixtures", "store_snapshot.json")


def capture():
    products = live_catalogue._fetch_raw_products()
    with live_catalogue._client() as client:
        content = {p["handle"]: live_catalogue._fetch_product_content(p["handle"], client) for p in products}
    missing = [h for h, c in content.items() if c is None]
    snapshot = {
        "store_url": live_catalogue.store_url(),
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "products": products,
        "content": content,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)
    print(f"Saved {len(products)} products to {OUT}" + (f"; no page copy for: {', '.join(missing)}" if missing else ""))


if __name__ == "__main__":
    capture()
