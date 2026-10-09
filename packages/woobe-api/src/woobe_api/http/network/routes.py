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


from modules.network.entrypoint import build_network_history_reader, build_network_asac_drafts, build_network_asac_candidates, build_network_asac_evaluations
from woobe_api.http.shared.asac_draft_routes import draft_router
from woobe_api.http.shared.asac_history_routes import history_router

router = APIRouter()
router.include_router(draft_router("/projects/{project_id}/networks/{resource_id}/asac", build_network_asac_drafts, "Network", build_network_asac_candidates, build_network_asac_evaluations))
router.include_router(history_router("/projects/{project_id}/networks/{resource_id}/asac", build_network_history_reader, "Network"))
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
