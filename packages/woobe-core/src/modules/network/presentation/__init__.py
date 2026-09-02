from fastapi import APIRouter, Depends

from modules.network.presentation.diagnostics_routes import router as diagnostics_router
from modules.network.presentation.management_routes import router as management_router
from modules.network.presentation.reattach_routes import router as reattach_router
from modules.network.presentation.rerun_routes import router as rerun_router
from modules.network.presentation.routes import router as runtime_router
from modules.network.presentation.runtime_environment_dependency import (
    enforce_network_runtime_environment,
)


router = APIRouter()
router.include_router(
    runtime_router,
    dependencies=[Depends(enforce_network_runtime_environment)],
)
router.include_router(reattach_router)
router.include_router(rerun_router)
router.include_router(management_router)
router.include_router(diagnostics_router)

__all__ = ["router"]
