"""Set the admin login for the reports area in backend/.env (run from the backend folder).

    python scripts/set_admin_password.py admin@example.com        # prompts for the password (hidden)
    ADMIN_PASSWORD=... python scripts/set_admin_password.py admin@example.com   # non-interactive

Writes ADMIN_EMAIL and ADMIN_PASSWORD_HASH (PBKDF2 hash, never the password itself),
and generates JWT_SECRET if it is missing or too short. Restart the backend afterwards.
"""

import getpass
import os
import re
import secrets
import sys

sys.path.append(os.getcwd())

from app.core.security import hash_password  # noqa: E402

ENV_PATH = ".env"


def set_vars(values: dict[str, str]) -> None:
    lines = open(ENV_PATH, encoding="utf-8").read().splitlines() if os.path.exists(ENV_PATH) else []
    for key, value in values.items():
        pattern = re.compile(rf"^\s*{key}\s*=")
        for i, line in enumerate(lines):
            if pattern.match(line):
                lines[i] = f"{key}={value}"
                break
        else:
            lines.append(f"{key}={value}")
    with open(ENV_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        sys.exit("usage: python scripts/set_admin_password.py <admin-email>")
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Admin password (min 12 characters): ")
    if len(password) < 12:
        sys.exit("Password must be at least 12 characters.")

    # single quotes: the hash contains "$", which .env loaders would otherwise try to expand
    values = {"ADMIN_EMAIL": sys.argv[1].strip().lower(), "ADMIN_PASSWORD_HASH": f"'{hash_password(password)}'"}
    current = open(ENV_PATH, encoding="utf-8").read() if os.path.exists(ENV_PATH) else ""
    secret = re.search(r"^\s*JWT_SECRET\s*=(.*)$", current, re.M)
    if not secret or len(secret.group(1).strip()) < 32:
        values["JWT_SECRET"] = secrets.token_urlsafe(48)
    set_vars(values)
    print(f"Updated {ENV_PATH}: {', '.join(values)} (values not shown). Restart the backend to apply.")


if __name__ == "__main__":
    main()
