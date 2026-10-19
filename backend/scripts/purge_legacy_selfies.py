"""
NO SELFIE STORAGE clean-up for photos saved BEFORE photos stopped being stored.

Older scans kept the photo on disk under app/uploads/<scan id>/<angle>.jpg and its path in scan_frames.storage_key.
New scans keep neither (storage_key = "not-stored"). This script removes what the old scans left behind:

- the photo files under app/uploads/ (only .jpg/.jpeg/.png/.webp files, only inside that folder);
- the photo path in scan_frames.storage_key, replaced by "not-stored".

Everything else is kept: users, scans, scan_frames rows and their quality scores, skin profiles, reports, deliveries.

By default it only REPORTS what it would remove (nothing is changed):

    python scripts/purge_legacy_selfies.py

Removing is permanent and needs --apply (run it only once the owner has approved it):

    python scripts/purge_legacy_selfies.py --apply

"""

import argparse
import os
import stat
import sys

sys.path.append(os.getcwd())

from sqlalchemy import text  # noqa: E402

from app.db.session import engine  # noqa: E402
from app.services.storage import UPLOAD_DIR  # noqa: E402

PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
NOT_STORED = "not-stored"


def photo_files() -> list[str]:
    found = []
    for root, _, names in os.walk(UPLOAD_DIR):
        found += [os.path.join(root, n) for n in names if n.lower().endswith(PHOTO_EXTENSIONS)]
    return sorted(found)


def main():
    parser = argparse.ArgumentParser(description="Remove photos stored by older scans (dry run by default).")
    parser.add_argument("--apply", action="store_true", help="really delete the files and clear the stored paths")
    args = parser.parse_args()

    files = photo_files()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT count(*) FROM scan_frames WHERE storage_key <> :ns"), {"ns": NOT_STORED}).scalar()
        total = conn.execute(text("SELECT count(*) FROM scan_frames")).scalar()
    print(f"Photo files under {UPLOAD_DIR}: {len(files)}")
    print(f"scan_frames rows still holding a photo path: {rows} (of {total}; the rows themselves are kept)")

    if not args.apply:
        print("\nDry run: nothing was changed. Re-run with --apply to remove them (permanent).")
        return

    with engine.begin() as conn:  # the paths first, in one transaction: no row points at a deleted file
        cleared = conn.execute(text("UPDATE scan_frames SET storage_key = :ns WHERE storage_key <> :ns"), {"ns": NOT_STORED}).rowcount
    removed = 0
    upload_root = os.path.realpath(UPLOAD_DIR)
    for path in files:
        if os.path.commonpath([upload_root, os.path.realpath(path)]) != upload_root:
            continue  # never outside app/uploads/
        os.remove(path)
        removed += 1
    for root, dirs, names in os.walk(UPLOAD_DIR, topdown=False):  # empty per-scan folders
        if root != UPLOAD_DIR and not os.listdir(root):
            os.chmod(root, stat.S_IWRITE)  # OneDrive marks synced folders read-only, and Windows then refuses rmdir
            os.rmdir(root)
    print(f"\nCleared {cleared} stored photo paths and deleted {removed} photo files.")


if __name__ == "__main__":
    main()
