"""Grant (or revoke) moderator access for reviewing seller listings.

Usage:
    python -m scripts.grant_admin --email you@example.com
    python -m scripts.grant_admin --email you@example.com --revoke
    python -m scripts.grant_admin --list
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app import models
from app.db import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage MODA moderators")
    parser.add_argument("--email")
    parser.add_argument("--revoke", action="store_true")
    parser.add_argument("--list", action="store_true", help="list current moderators")
    args = parser.parse_args()

    db = SessionLocal()
    if args.list:
        admins = db.scalars(select(models.User).where(models.User.is_admin)).all()
        print(f"{len(admins)} moderator(s):")
        for a in admins:
            print(f"  {a.username} <{a.email}>")
        db.close()
        return

    if not args.email:
        sys.exit("Pass --email you@example.com (or --list)")

    user = db.scalar(select(models.User).where(models.User.email == args.email))
    if not user:
        db.close()
        sys.exit(f"No user with email {args.email}")

    user.is_admin = not args.revoke
    db.commit()
    print(f"{user.username} <{user.email}> is_admin={user.is_admin}")
    db.close()


if __name__ == "__main__":
    main()
