from fastapi import APIRouter

from app.domain.health.api import router as health_routes

router = APIRouter()
router.include_router(health_routes)
