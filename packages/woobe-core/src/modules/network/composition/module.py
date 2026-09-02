from modules.network.presentation import router as legacy_network_router
from modules.network.presentation.http.diagnostics_routes import router as diagnostics_router
from modules.network.presentation.http.rerun_routes import router as rerun_router
from modules.network.presentation.http.resource_routes import router as resource_router


NETWORK_HTTP_ROUTERS = (
    resource_router,
    rerun_router,
    diagnostics_router,
    legacy_network_router,
)

__all__ = ["NETWORK_HTTP_ROUTERS"]
