from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth.model import User
from app.domain.permission.model import Permission


class PermissionService:
    @staticmethod
    async def get_user_permissions(db: AsyncSession, user_id: int) -> set[str]:
        """Get all effective permissions for a user (from all their roles)."""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return set()

        # Collect all permission codes from all roles
        permissions = set()
        for role in user.roles:
            for permission in role.permissions:
                permissions.add(permission.code)

        return permissions

    @staticmethod
    async def has_permission(db: AsyncSession, user_id: int, permission_code: str) -> bool:
        """Check if user has a specific permission."""
        permissions = await PermissionService.get_user_permissions(db, user_id)
        return permission_code in permissions

    @staticmethod
    async def list_permissions(db: AsyncSession) -> list[Permission]:
        """Fetch all available permissions from the system."""
        result = await db.execute(select(Permission).order_by(Permission.code))
        return list(result.scalars().all())
