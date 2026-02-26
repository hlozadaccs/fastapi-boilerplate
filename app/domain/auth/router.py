from fastapi import APIRouter

from app.domain.auth.api import router as auth_routes

router = APIRouter()
router.include_router(auth_routes)
