from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Paginator
from app.core.responses import PaginatedData
from app.core.schemas import PaginationParams
from app.domain.auth.dependencies import require_permission
from app.domain.auth.model import Role
from app.domain.role.schema import RoleCreate, RoleRead, RoleUpdate
from app.domain.role.service import RoleService
from app.infrastructure.db.dependencies import get_db

router = APIRouter(prefix="/roles", tags=["roles"])
role_service = RoleService()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=RoleRead)
async def create_role(
    payload: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("role:create")),
):
    try:
        role = await role_service.create_role(db, payload)
        await db.commit()
        return RoleRead(
            id=role.id,
            name=role.name,
            description=role.description,
            created_at=role.created_at,
            updated_at=role.updated_at,
            permissions=[p.code for p in role.permissions],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{role_id}", response_model=RoleRead)
async def get_role(
    role_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("role:read")),
):
    role = await role_service.get_role_with_permissions(db, role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    return RoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        created_at=role.created_at,
        updated_at=role.updated_at,
        permissions=[p.code for p in role.permissions],
    )


@router.get("", response_model=PaginatedData[RoleRead])
async def list_roles(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("role:read")),
):
    paginator: Paginator[Role] = Paginator(page=pagination.page, page_size=pagination.page_size)
    query = select(Role)
    result = await paginator.paginate(db, query)

    # Transform to include permissions
    items_with_perms = [
        RoleRead(
            id=role.id,
            name=role.name,
            description=role.description,
            created_at=role.created_at,
            updated_at=role.updated_at,
            permissions=[p.code for p in role.permissions],
        )
        for role in result.items
    ]

    return PaginatedData(
        items=items_with_perms,
        pagination=result.pagination,
    )


@router.put("/{role_id}", response_model=RoleRead)
async def update_role(
    payload: Annotated[RoleUpdate, Body()],
    role_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("role:update")),
):
    try:
        role = await role_service.update_role(db, role_id, payload)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

        await db.commit()
        return RoleRead(
            id=role.id,
            name=role.name,
            description=role.description,
            created_at=role.created_at,
            updated_at=role.updated_at,
            permissions=[p.code for p in role.permissions],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/{role_id}", response_model=RoleRead)
async def partial_update_role(
    payload: Annotated[RoleUpdate, Body()],
    role_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("role:update")),
):
    try:
        role = await role_service.update_role(db, role_id, payload)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

        await db.commit()
        return RoleRead(
            id=role.id,
            name=role.name,
            description=role.description,
            created_at=role.created_at,
            updated_at=role.updated_at,
            permissions=[p.code for p in role.permissions],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("role:delete")),
):
    deleted = await role_service.delete(db, role_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    await db.commit()
