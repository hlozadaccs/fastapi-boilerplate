from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.permission.model import Permission
from app.domain.role.model import Role
from app.domain.role.schema import RoleCreate, RoleUpdate
from app.infrastructure.db.repository import BaseRepository


class RoleService(BaseRepository[Role]):
    def __init__(self):
        super().__init__(Role)

    async def create_role(self, db: AsyncSession, payload: RoleCreate) -> Role:
        """Create role with permissions."""
        # Check if role name already exists
        result = await db.execute(select(Role).where(Role.name == payload.name))
        if result.scalar_one_or_none():
            raise ValueError(f"Role '{payload.name}' already exists")

        # Create role
        role = Role(name=payload.name, description=payload.description)
        role.permissions = []  # Initialize collection to avoid lazy load on first access
        db.add(role)
        await db.flush()

        # Assign permissions
        if payload.permissions:
            result = await db.execute(
                select(Permission).where(Permission.code.in_(payload.permissions))
            )
            permissions: list[Permission] = list(result.scalars().all())  # type: ignore
            found_codes = {p.code for p in permissions}
            invalid_codes = set(payload.permissions) - found_codes
            if invalid_codes:
                raise ValueError(f"Invalid permission codes: {', '.join(sorted(invalid_codes))}")
            role.permissions.extend(permissions)

        await db.flush()

        # Reload with permissions explicitly using selectinload
        result = await db.execute(
            select(Role).where(Role.id == role.id).options(selectinload(Role.permissions))
        )
        return result.scalar_one()

    async def update_role(self, db: AsyncSession, role_id: int, payload: RoleUpdate) -> Role | None:
        """Update role and optionally its permissions."""
        result = await db.execute(
            select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
        )
        role = result.scalar_one_or_none()

        if not role:
            return None

        # Update basic fields
        if payload.name is not None:
            # Check name uniqueness
            result = await db.execute(
                select(Role).where(Role.name == payload.name, Role.id != role_id)
            )
            if result.scalar_one_or_none():
                raise ValueError(f"Role '{payload.name}' already exists")
            role.name = payload.name

        if payload.description is not None:
            role.description = payload.description

        # Update permissions if provided
        if payload.permissions is not None:
            result = await db.execute(
                select(Permission).where(Permission.code.in_(payload.permissions))
            )
            permissions: list[Permission] = list(result.scalars().all())  # type: ignore
            found_codes = {p.code for p in permissions}
            invalid_codes = set(payload.permissions) - found_codes
            if invalid_codes:
                raise ValueError(f"Invalid permission codes: {', '.join(sorted(invalid_codes))}")
            role.permissions.clear()
            role.permissions.extend(permissions)

        await db.flush()

        # Reload with permissions explicitly
        await db.refresh(role, attribute_names=["permissions"])
        return role

    async def get_role_with_permissions(self, db: AsyncSession, role_id: int) -> Role | None:
        """Get role with permissions loaded."""
        result = await db.execute(
            select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def list_roles_with_permissions(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> list[Role]:
        """List roles with permissions loaded."""
        result = await db.execute(
            select(Role).options(selectinload(Role.permissions)).offset(skip).limit(limit)
        )
        return list(result.scalars().all())
