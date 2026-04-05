from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import PaginatedData
from app.core.schemas import PaginationParams
from app.domain.auth.dependencies import require_permission
from app.domain.permission.schema import PermissionRead
from app.domain.permission.service import PermissionService
from app.infrastructure.db.dependencies import get_db

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("", response_model=PaginatedData[PermissionRead])
async def list_permissions(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("role:read")),
):
    """List all available system permissions with pagination (Admin only)."""
    return await PermissionService.list_permissions(
        db, page=pagination.page, page_size=pagination.page_size
    )
