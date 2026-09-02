from modules.network.presentation import router as legacy_network_router
from modules.network.presentation.http.compatibility_routes import router as compatibility_router
from modules.network.presentation.http.diagnostics_routes import router as diagnostics_router
from modules.network.presentation.http.draft_routes import router as draft_router
from modules.network.presentation.http.history_routes import router as history_router
from modules.network.presentation.http.legacy_version_routes import router as legacy_version_router
from modules.network.presentation.http.management_routes import router as management_router
from modules.network.presentation.http.promotion_routes import router as promotion_router
from modules.network.presentation.http.rerun_routes import router as rerun_router
from modules.network.presentation.http.resource_routes import router as resource_router
from modules.network.presentation.http.session_routes import router as session_router


NETWORK_HTTP_ROUTERS = (
    resource_router,
    compatibility_router,
    draft_router,
    promotion_router,
    legacy_version_router,
    rerun_router,
    diagnostics_router,
    management_router,
    history_router,
    session_router,
    legacy_network_router,
)

__all__ = ["NETWORK_HTTP_ROUTERS"]
