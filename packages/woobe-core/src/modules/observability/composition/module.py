from modules.observability.presentation.http.routes import router as observability_router

OBSERVABILITY_HTTP_ROUTERS = (observability_router,)

__all__ = ["OBSERVABILITY_HTTP_ROUTERS"]
