from fastapi import APIRouter

from modules.network.presentation.management_routes import router as management_router
from modules.network.presentation.resource_routes import router as resource_router
from modules.network.presentation.routes import router as runtime_router


router = APIRouter()
router.include_router(resource_router)
router.include_router(runtime_router)
router.include_router(management_router)

__all__ = ["router"]
