from fastapi import APIRouter

from modules.network.presentation.reattach_routes import router as reattach_router
from modules.network.presentation.routes import router as runtime_router


router = APIRouter()
router.include_router(runtime_router)
router.include_router(reattach_router)

__all__ = ["router"]
