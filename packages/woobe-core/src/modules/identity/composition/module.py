from modules.identity.presentation.instance_routes import router as instance_router
from modules.identity.presentation.routes import router as identity_router

IDENTITY_PUBLIC_HTTP_ROUTERS = (instance_router,)
IDENTITY_HTTP_ROUTERS = (identity_router,)

__all__ = ["IDENTITY_HTTP_ROUTERS", "IDENTITY_PUBLIC_HTTP_ROUTERS"]
