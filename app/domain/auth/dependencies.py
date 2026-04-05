from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import decode_token
from app.domain.auth.model import User
from app.domain.auth.service import PermissionService
from app.infrastructure.db.dependencies import get_db

security = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> int:
    """Extract and validate user_id from access token and verify user state."""
    try:
        token = credentials.credentials
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    # Check if user exists and is active
    result = await db.execute(select(User.is_active).where(User.id == user_id))
    is_active = result.scalar_one_or_none()
    
    if is_active is None or not is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user_id


def require_permission(permission_code: str):
    """Dependency factory to check if user has required permission."""

    async def permission_checker(
        user_id: int = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db),
    ) -> int:
        # Check if user is admin
        result = await db.execute(select(User.is_admin).where(User.id == user_id))
        is_admin = result.scalar_one_or_none()
        
        if is_admin:
            return user_id
        
        # Check permission for non-admin users
        has_perm = await PermissionService.has_permission(db, user_id, permission_code)
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_code} required",
            )
        return user_id

    return permission_checker
