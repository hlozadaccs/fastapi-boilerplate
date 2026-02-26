from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.base import Base


class BaseRepository[ModelType: Base]:
    """Base repository with common CRUD operations."""

    def __init__(self, model: type[ModelType]):
        self.model = model

    async def get_by_id(self, db: AsyncSession, id: int) -> ModelType | None:
        """Get entity by ID."""
        result = await db.execute(select(self.model).where(self.model.id == id))  # type: ignore[attr-defined]
        return result.scalar_one_or_none()

    async def list(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """List entities with pagination."""
        result = await db.execute(select(self.model).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, entity: ModelType) -> ModelType:
        """Create new entity."""
        db.add(entity)
        await db.flush()
        return entity

    async def delete(self, db: AsyncSession, id: int) -> bool:
        """Delete entity by ID."""
        entity = await self.get_by_id(db, id)
        if not entity:
            return False

        await db.delete(entity)
        await db.flush()
        return True
