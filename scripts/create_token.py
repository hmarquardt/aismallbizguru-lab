#!/usr/bin/env python3
"""Generate a bearer token for API access."""

import json
import sys

from app.auth.tokens import generate_token, masked_token


def main() -> None:
    name = input("Token name: ").strip()
    if not name:
        print("Error: name is required", file=sys.stderr)
        raise SystemExit(1)

    scopes_raw = input("Scopes (JSON, e.g. {\"junk-drawer\": [\"read\", \"write\"]}, leave empty for all access): ").strip()
    if scopes_raw:
        try:
            scopes = json.loads(scopes_raw)
        except json.JSONDecodeError:
            print("Error: invalid JSON for scopes", file=sys.stderr)
            raise SystemExit(1)
    else:
        scopes = {}

    raw, token_hash = generate_token()

    print()
    print(f"Token name: {name}")
    print(f"Token hash (store this): {token_hash}")
    print(f"Raw token (show once only): {raw}")
    if scopes:
        print(f"Scopes: {json.dumps(scopes)}")
    else:
        print("Scopes: all")
    print()
    print("WARNING: The raw token above will NOT be shown again. Store it securely.")
    print(f"Add the token hash to your database manually for now.")


if __name__ == "__main__":
    main()