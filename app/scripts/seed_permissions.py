"""
Seed script to populate initial roles and permissions.

Run with: poetry run python -m app.scripts.seed_permissions
"""

import asyncio

from sqlalchemy import select

from app.core.permissions import ensure_model_permissions
from app.domain.auth.model import Permission, Role, role_permissions
from app.infrastructure.db.session import AsyncSessionLocal

# Define resources and their actions
RESOURCES = {
    "user": ["create", "read", "update", "delete"],
    "role": ["create", "read", "update", "delete"],
    "permission": ["read"],  # Read-only
}

# Define roles and their permissions
ROLES = {
    "admin": {
        "description": "Administrator with full access",
        "permissions": "*",  # All permissions
    },
    "user": {
        "description": "Regular user with limited access",
        "permissions": ["user:read"],
    },
}


async def seed_permissions():
    """Create initial permissions and roles."""
    async with AsyncSessionLocal() as db:
        # Check if already seeded
        result = await db.execute(select(Role))
        if result.scalars().first():
            print("✓ Permissions already seeded")
            return

        # Create permissions for each resource
        all_permissions = []
        for resource, actions in RESOURCES.items():
            for action in actions:
                code = f"{resource}:{action}"
                perm = Permission(
                    code=code,
                    description=f"{action.capitalize()} {resource}",
                )
                db.add(perm)
                all_permissions.append(perm)

        await db.flush()

        # Create roles and assign permissions
        for role_name, role_config in ROLES.items():
            role = Role(
                name=role_name,
                description=role_config["description"],
            )
            db.add(role)
            await db.flush()

            # Assign permissions
            if role_config["permissions"] == "*":
                # Assign all permissions
                perm_ids = [p.id for p in all_permissions]
            else:
                # Assign specific permissions
                perm_ids = [
                    p.id for p in all_permissions
                    if p.code in role_config["permissions"]
                ]

            if perm_ids:
                await db.execute(
                    role_permissions.insert().values(
                        [{"role_id": role.id, "permission_id": pid} for pid in perm_ids]
                    )
                )

        await db.commit()
        print("Permissions and roles seeded successfully")
        print(f"  - Created {len(all_permissions)} permissions")
        print(f"  - Created {len(ROLES)} roles")
        for resource, actions in RESOURCES.items():
            print(f"  - {resource}: {', '.join(actions)}")

if __name__ == "__main__":
    asyncio.run(seed_permissions())
