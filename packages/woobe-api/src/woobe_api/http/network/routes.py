from fastapi import APIRouter, Depends

from woobe_api.http.network.diagnostics_routes import router as diagnostics_router
from woobe_api.http.network.management_routes import router as management_router
from woobe_api.http.network.reattach_routes import router as reattach_router
from woobe_api.http.network.rerun_routes import router as rerun_router
from woobe_api.http.network.resource_routes import router as resource_router
from woobe_api.http.network.runtime_routes import router as runtime_router
from woobe_api.http.network.runtime_environment_dependency import (
    enforce_network_runtime_environment,
)


router = APIRouter()
router.include_router(resource_router)
router.include_router(
    runtime_router,
    dependencies=[Depends(enforce_network_runtime_environment)],
)
router.include_router(reattach_router)
router.include_router(rerun_router)
router.include_router(management_router)
router.include_router(diagnostics_router)

__all__ = ["router"]
