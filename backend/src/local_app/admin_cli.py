from __future__ import annotations

import argparse
import json
import sys
from typing import Callable

from local_app.dynamodb import ensure_tables
from local_app.local_auth import (
    LocalAdminNotFoundError,
    LocalAdminValidationError,
    LocalDuplicateAdminError,
    change_admin_password,
    create_admin_user,
    disable_admin_user,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage local-only administrator users.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a local administrator.")
    create_parser.add_argument("email")
    create_parser.add_argument("password")
    create_parser.add_argument("display_name")

    disable_parser = subparsers.add_parser("disable", help="Disable a local administrator.")
    disable_parser.add_argument("email")

    password_parser = subparsers.add_parser("change-password", help="Change a local administrator password.")
    password_parser.add_argument("email")
    password_parser.add_argument("password")

    args = parser.parse_args()
    ensure_tables()
    try:
        command_handlers: dict[str, Callable[[], dict[str, object]]] = {
            "create": lambda: create_admin_user(args.email, args.password, args.display_name),
            "disable": lambda: disable_admin_user(args.email),
            "change-password": lambda: change_admin_password(args.email, args.password),
        }
        result = command_handlers[args.command]()
    except LocalDuplicateAdminError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (LocalAdminNotFoundError, LocalAdminValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
