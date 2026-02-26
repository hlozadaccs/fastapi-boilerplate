from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession]:
    """
    Provides a SQLAlchemy AsyncSession per request.

    - Commits if everything is OK
    - Rollbacks on exception
    - Always closes the session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
