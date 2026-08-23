from fastapi import APIRouter, Depends

from modules.network.presentation.diagnostics_routes import router as diagnostics_router
from modules.network.presentation.management_routes import router as management_router
from modules.network.presentation.resource_routes import router as resource_router
from modules.network.presentation.routes import router as runtime_router
from modules.network.presentation.runtime_environment_dependency import (
    enforce_network_runtime_environment,
)


router = APIRouter()
router.include_router(resource_router)
router.include_router(
    runtime_router,
    dependencies=[Depends(enforce_network_runtime_environment)],
)
router.include_router(management_router)
router.include_router(diagnostics_router)

__all__ = ["router"]
