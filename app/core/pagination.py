from math import ceil
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Select

from app.core.responses import PaginatedData, PaginationMeta

T = TypeVar("T")


class Paginator[T]:
    """Reusable paginator for SQLAlchemy queries."""

    def __init__(self, page: int = 1, page_size: int = 20):
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 100)  # Max 100 items per page

    @property
    def offset(self) -> int:
        """Calculate offset for query."""
        return (self.page - 1) * self.page_size

    async def paginate(
        self,
        db: AsyncSession,
        query: Select,
    ) -> PaginatedData[T]:
        """Execute paginated query and return structured data."""
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Get paginated items
        paginated_query = query.offset(self.offset).limit(self.page_size)
        result = await db.execute(paginated_query)
        items = list(result.scalars().all())

        # Calculate pagination metadata
        total_pages = ceil(total / self.page_size) if total > 0 else 0

        return PaginatedData(
            items=items,
            pagination=PaginationMeta(
                total=total,
                page=self.page,
                page_size=self.page_size,
                total_pages=total_pages,
            ),
        )
