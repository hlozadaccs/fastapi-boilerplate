from fastapi import APIRouter

from app.domain.user.api import router as user_routes

router = APIRouter()
router.include_router(user_routes)
