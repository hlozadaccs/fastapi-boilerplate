from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Paginator
from app.core.responses import PaginatedData
from app.core.schemas import PaginationParams
from app.domain.auth.dependencies import require_permission
from app.domain.auth.model import User
from app.domain.user.schema import UserCreate, UserRead, UserUpdate
from app.domain.user.service import UserService
from app.infrastructure.db.dependencies import get_db

router = APIRouter(prefix="/users", tags=["users"])
user_service = UserService()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserRead)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("user:create")),
):
    try:
        return await user_service.create_user(
            db=db,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password=payload.password,
            is_admin=payload.is_admin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("user:read")),
):
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("", response_model=PaginatedData[UserRead])
async def list_users(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("user:read")),
):
    paginator = Paginator(page=pagination.page, page_size=pagination.page_size)
    query = select(User)
    return await paginator.paginate(db, query)


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int = Path(..., gt=0),
    payload: UserUpdate = ...,
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("user:update")),
):
    try:
        user = await user_service.update_user(db, user_id, payload)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/{user_id}", response_model=UserRead)
async def partial_update_user(
    user_id: int = Path(..., gt=0),
    payload: UserUpdate = ...,
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("user:update")),
):
    try:
        user = await user_service.update_user(db, user_id, payload)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("user:delete")),
):
    deleted = await user_service.delete(db, user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
