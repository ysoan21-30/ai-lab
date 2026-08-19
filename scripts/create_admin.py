#!/usr/bin/env python
"""Promote a user to admin, or create one if they don't exist.

Usage:
    python scripts/create_admin.py admin@example.com password123
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.auth.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.models import PlanTier, User  # noqa: E402


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/create_admin.py <email> <password>")
        sys.exit(1)

    email, password = sys.argv[1].lower(), sys.argv[2]
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.is_admin = True
            print(f"Existing user {email} promoted to admin.")
        else:
            user = User(
                email=email,
                hashed_password=hash_password(password),
                is_admin=True,
                plan=PlanTier.TEAM,
            )
            db.add(user)
            print(f"Created new admin user {email}.")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
