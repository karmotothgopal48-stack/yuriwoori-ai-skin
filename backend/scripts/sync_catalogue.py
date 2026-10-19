"""
Records the live YuriWoori catalogue (https://yuriwoori.com) in the local products table.

The app does not need this to work: it reads products live (app/services/live_catalogue.py) and records
each product when it serves it. Run this to record the whole catalogue at once, e.g. before
scripts/build_embeddings.py so the coach can find every product:

    python scripts/sync_catalogue.py

Rows are keyed by Shopify handle (the same rows the app uses). Products the store no longer lists are
marked inactive, never deleted (saved routines and carts may point at them).
"""

import os
import sys

sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.services.live_catalogue import get_catalogue
from app.services.product_records import ensure_product_rows, mark_unlisted_inactive


def sync():
    catalogue = get_catalogue()
    db = SessionLocal()
    try:
        rows = ensure_product_rows(db, catalogue.products)
        inactive = mark_unlisted_inactive(db, catalogue)
        db.commit()
    finally:
        db.close()
    unread = f" Product pages not read (not matched to scans until the next refresh): {', '.join(catalogue.unread_pages)}." if catalogue.unread_pages else ""
    print(f"Recorded {len(rows)} live products (fetched {catalogue.fetched_at}); {inactive} no longer listed, marked inactive.{unread}")


if __name__ == "__main__":
    sync()
