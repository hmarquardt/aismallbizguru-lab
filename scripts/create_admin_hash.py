#!/usr/bin/env python3
"""Generate an Argon2 password hash for ADMIN_PASSWORD_HASH."""

import sys
from getpass import getpass

from app.auth.password import hash_password


def main() -> None:
    password = getpass("Enter password: ").strip()
    if not password:
        print("Error: empty password", file=sys.stderr)
        raise SystemExit(1)

    if len(password) < 8:
        print("Error: password must be at least 8 characters", file=sys.stderr)
        raise SystemExit(1)

    confirm = getpass("Confirm password: ").strip()
    if confirm != password:
        print("Error: passwords do not match", file=sys.stderr)
        raise SystemExit(1)

    hashed = hash_password(password)
    print()
    print(f"ADMIN_PASSWORD_HASH={hashed}")
    print()
    print("Add the above line to your .env file.")


if __name__ == "__main__":
    main()
