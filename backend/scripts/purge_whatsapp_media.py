"""
Delete report PDFs still held in WhatsApp's media store (uploads are normally deleted when WhatsApp's webhook reports
the message delivered, read or failed, or right away when a message couldn't be sent). This catches the rest, e.g.
when the webhook isn't set up. Only uploads older than --days (default 7) are touched.

    python scripts/purge_whatsapp_media.py            # DRY RUN: how many uploads would be deleted
    python scripts/purge_whatsapp_media.py --apply    # delete them at WhatsApp (DELETE /{media-id})

Nothing about the customer or the delivery status is removed; only the stored media id is cleared once deleted.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from app.db.models import ResultDelivery  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import delivery  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete leftover report PDFs from WhatsApp's media store")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        older = timedelta(days=args.days)
        due = (db.query(ResultDelivery).filter(ResultDelivery.provider_media_id.isnot(None),
                                               ResultDelivery.updated_at < datetime.utcnow() - older).count())
        held = db.query(ResultDelivery).filter(ResultDelivery.provider_media_id.isnot(None)).count()
        print(f"uploads still held at WhatsApp: {held} | older than {args.days} days: {due}")
        if not args.apply:
            print("Dry run: nothing was deleted. Add --apply to delete them.")
            return 0
        if not delivery.configured("whatsapp"):
            print("WhatsApp isn't configured: nothing can be deleted.")
            return 1
        print(delivery.purge_whatsapp_media(db, older))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
