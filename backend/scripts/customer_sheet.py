"""
Customer follow-up spreadsheet (Google Sheets, service account): checks, tests, retries and reconciling.
Run from the backend folder. Nothing here prints the key, a token, or customer details.

    python scripts/customer_sheet.py check        # settings and key file only, no network
    python scripts/customer_sheet.py test         # read-only: token, spreadsheet access, worksheet columns (writes nothing)
    python scripts/customer_sheet.py setup-sheet --confirm  # EMPTY sheet only: name the tab, write the 13 headers
    python scripts/customer_sheet.py test-write --confirm [--cleanup]  # ONE fake row (TEST-...) twice; --cleanup deletes it
    python scripts/customer_sheet.py status       # queued / written / failed counts and error codes
    python scripts/customer_sheet.py sync         # write the rows that are due now
    python scripts/customer_sheet.py retry        # make failed rows due now, then sync
    python scripts/customer_sheet.py reconcile    # DRY RUN: customers who would be queued
    python scripts/customer_sheet.py reconcile --apply [--all]   # queue them (exports real customers), then sync

"""

import argparse
import os
import sys

sys.path.append(os.getcwd())

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import customer_sheet, google_sheets  # noqa: E402
from app.services.google_sheets import SheetsError  # noqa: E402


def check() -> int:
    problems = google_sheets.config_problems()
    print(f"CUSTOMER_SHEET_SYNC_ENABLED: {'true' if settings.customer_sheet_sync_enabled else 'false (rows are queued, not written)'}")
    print(f"GOOGLE_SHEETS_SPREADSHEET_ID: {'configured' if settings.google_sheets_spreadsheet_id.strip() else 'missing'}")
    print(f"GOOGLE_SHEETS_WORKSHEET_NAME: {settings.google_sheets_worksheet_name}")
    print(f"GOOGLE_SERVICE_ACCOUNT_FILE: {'configured' if settings.google_service_account_file.strip() else 'missing'}")
    email = google_sheets.service_account_email()
    print(f"service account to share the sheet with: {email or '(key file not readable yet)'}")
    print(f"google-auth package: {'installed' if google_sheets.google_auth_available() else 'not installed'}")
    for p in problems:
        print(f"  problem: {p}")
    for w in google_sheets.config_warnings():
        print(f"  warning: {w}")
    print("OK" if not problems else "Not ready")
    return 0 if not problems and email else 1


def test() -> int:
    checks = customer_sheet.connection_test()
    for name, ok, detail in checks:
        print(f"[{'ok' if ok else 'FAIL'}] {name}: {detail}")
    print("Read-only test: nothing was written.")
    return 0 if all(ok for _, ok, _ in checks) else 1


def test_write(confirmed: bool, cleanup: bool) -> int:
    if not confirmed:
        print("This writes one fake row (Customer ID TEST-...) to the spreadsheet. Re-run with --confirm to do it.")
        return 1
    problems = google_sheets.config_problems()
    if problems:
        print("Not ready: " + "; ".join(problems))
        return 1
    try:
        for line in customer_sheet.dummy_write(cleanup=cleanup):
            print(line)
    except SheetsError as exc:
        print(f"FAIL: {exc.code}")
        return 1
    print("Done. No database record or real customer was used." + ("" if cleanup else " Delete the TEST- row in the sheet when finished."))
    return 0


def setup_sheet(confirmed: bool) -> int:
    if not confirmed:
        print("This names the empty spreadsheet's tab and writes the 13 column headers. Re-run with --confirm to do it.")
        return 1
    try:
        for line in customer_sheet.setup_worksheet():
            print(line)
    except SheetsError as exc:
        print(f"FAIL: {exc.code}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Customer follow-up spreadsheet tools")
    parser.add_argument("command", choices=("check", "test", "setup-sheet", "test-write", "status", "sync", "retry", "reconcile"))
    parser.add_argument("--apply", action="store_true", help="reconcile: queue the customers (otherwise a dry run)")
    parser.add_argument("--all", action="store_true", help="reconcile: rewrite every eligible customer's row")
    parser.add_argument("--confirm", action="store_true", help="setup-sheet / test-write: really write")
    parser.add_argument("--cleanup", action="store_true", help="test-write: delete the fake row afterwards")
    args = parser.parse_args()
    if args.command == "check":
        return check()
    if args.command == "test":
        return test()
    if args.command == "setup-sheet":
        return setup_sheet(args.confirm)
    if args.command == "test-write":
        return test_write(args.confirm, args.cleanup)
    db = SessionLocal()
    try:
        if args.command == "status":
            print(customer_sheet.status_counts(db))
        elif args.command == "sync":
            print(customer_sheet.process_due(db, limit=200))
        elif args.command == "retry":
            print(f"failed rows made due now: {customer_sheet.retry_failed(db)}")
            print(customer_sheet.process_due(db, limit=200))
        elif args.command == "reconcile":
            result = customer_sheet.reconcile(db, apply=args.apply, rewrite_all=args.all)
            print(result)
            if not args.apply:
                print("Dry run: nothing was queued or exported. Add --apply to queue them.")
            else:
                print(customer_sheet.process_due(db, limit=200))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
