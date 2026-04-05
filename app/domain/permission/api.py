from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth.dependencies import require_permission
from app.domain.permission.schema import PermissionRead
from app.domain.permission.service import PermissionService
from app.infrastructure.db.dependencies import get_db

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("", response_model=list[PermissionRead])
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("role:read")),
):
    """List all available system permissions (Admin only)."""
    return await PermissionService.list_permissions(db)
