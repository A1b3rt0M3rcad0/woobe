from modules.metering.presentation.http.routes import router as metering_router

METERING_HTTP_ROUTERS = (metering_router,)

__all__ = ["METERING_HTTP_ROUTERS"]
