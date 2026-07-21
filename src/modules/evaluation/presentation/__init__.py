from fastapi import APIRouter

from modules.evaluation.presentation.routes import router as resource_router
from modules.evaluation.presentation.version_routes import router as version_router

router = APIRouter()
router.include_router(resource_router)
router.include_router(version_router)

__all__ = ["router"]
