"""
Create user script.

Run with: poetry run python -m app.scripts.create_user --email user@example.com --password pass123 --first-name John --last-name Doe --admin
"""

import argparse
import asyncio

from sqlalchemy import insert, select

from app.core.security import hash_password
from app.domain.auth.model import Role, User, user_roles
from app.infrastructure.db.session import AsyncSessionLocal


async def create_user(
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    is_admin: bool = False,
):
    """Create user with optional admin privileges."""
    async with AsyncSessionLocal() as db:
        # Check if user exists
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            print(f"✗ User already exists: {email}")
            return

        # Create user
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=hash_password(password),
            is_admin=is_admin,
        )
        db.add(user)
        await db.flush()

        # Assign admin role if is_admin
        if is_admin:
            result = await db.execute(select(Role).where(Role.name == "admin"))
            admin_role = result.scalar_one_or_none()
            if admin_role:
                await db.execute(insert(user_roles).values(user_id=user.id, role_id=admin_role.id))

        await db.commit()
        role_type = "admin" if is_admin else "regular"
        print(f"✓ {role_type.capitalize()} user created: {user.email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new user")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--password", required=True, help="User password")
    parser.add_argument("--first-name", required=True, help="User first name")
    parser.add_argument("--last-name", required=True, help="User last name")
    parser.add_argument("--admin", action="store_true", help="Create as admin user")

    args = parser.parse_args()

    asyncio.run(
        create_user(
            email=args.email,
            password=args.password,
            first_name=args.first_name,
            last_name=args.last_name,
            is_admin=args.admin,
        )
    )
