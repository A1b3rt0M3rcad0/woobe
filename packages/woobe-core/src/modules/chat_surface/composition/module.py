from modules.chat_surface.presentation.reattach_routes import router as reattach_router
from modules.chat_surface.presentation.routes import router as chat_surface_router


CHAT_SURFACE_HTTP_ROUTERS = (
    chat_surface_router,
    reattach_router,
)

__all__ = ["CHAT_SURFACE_HTTP_ROUTERS"]
