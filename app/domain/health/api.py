from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.dependencies import get_db

router = APIRouter()


@router.get("/health", tags=["health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Healthcheck endpoint that also validates DB connectivity.
    """
    result = await db.execute(text("SELECT 1"))
    value = result.scalar_one()

    return {
        "status": "ok",
        "database": value,
    }
