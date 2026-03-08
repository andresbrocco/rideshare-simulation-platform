#!/usr/bin/env python3
"""Generate bcrypt password hashes for Trino's FILE authenticator.

Produces bcrypt hashes suitable for insertion into password.db.template
or direct use in a password.db file. The FILE authenticator requires
bcrypt hashes that begin with `$2y$` and use a minimum cost factor of 8.

Usage:
    ./venv/bin/python3 infrastructure/scripts/generate_trino_password_hash.py <password>
    ./venv/bin/python3 infrastructure/scripts/generate_trino_password_hash.py  # prompts for password

Output:
    The bcrypt hash string suitable for a password.db line, e.g.:
        $2y$10$...

Example password.db lines:
    admin:<output of this script for the admin password>
    visitor:<output of this script for the visitor password>

Exit codes:
    0 - Hash generated and printed to stdout
    1 - Error (bad arguments or bcrypt failure)
"""

import getpass
import sys


def generate_hash(password: str) -> str:
    """Generate a bcrypt hash compatible with Trino's FILE authenticator.

    Uses cost factor 10, which exceeds Trino's minimum requirement of 8.
    The hash prefix is `$2b$` as produced by the Python bcrypt library; Trino
    accepts both `$2b$` and `$2y$` variants.

    Args:
        password: The plaintext password to hash.

    Returns:
        The bcrypt hash string (e.g. `$2b$10$...`).
    """
    import bcrypt

    hashed: bytes = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10))
    return hashed.decode("utf-8")


def main() -> int:
    """Entry point: read password from args or prompt, print the hash.

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    if len(sys.argv) > 2:
        print(
            "Usage: generate_trino_password_hash.py [<password>]",
            file=sys.stderr,
        )
        return 1

    if len(sys.argv) == 2:
        password = sys.argv[1]
    else:
        password = getpass.getpass("Password: ")

    if not password:
        print("Error: password must not be empty.", file=sys.stderr)
        return 1

    try:
        result = generate_hash(password)
        print(result)
        return 0
    except Exception as exc:  # pragma: no cover
        print(f"Error generating hash: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
