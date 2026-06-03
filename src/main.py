from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from modules.ai.presentation.controllers import router as ai_router
from modules.billing.presentation.controllers import router as billing_router
from modules.core.presentation.controllers import router as core_router
from modules.identity.presentation.controllers import router as identity_router
from modules.knowledge.presentation.controllers import router as knowledge_router
from modules.metering.presentation.controllers import router as metering_router
from modules.observability.presentation.controllers import router as observability_router
from modules.runtime.presentation.controllers import router as runtime_router
from modules.tools.presentation.controllers import router as tools_router
from shared.infra.config import Settings
from shared.infra.database.session import create_engine
from shared.presentation.errors import (
    conflict_handler,
    domain_error_handler,
    not_found_handler,
    validation_handler,
)
from shared.domain.errors import ConflictError, DomainError, NotFoundError, ValidationError


def create_app() -> FastAPI:
    settings = Settings()

    app = FastAPI(
        title="ProjectRAI",
        description="Runtime AI Platform \u2014 Production-ready AI agent runtime",
        version="0.1.0",
    )

    app.state.settings = settings
    app.state.async_engine = create_engine(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(ConflictError, conflict_handler)
    app.add_exception_handler(ValidationError, validation_handler)

    app.include_router(identity_router)
    app.include_router(core_router)
    app.include_router(ai_router)
    app.include_router(knowledge_router)
    app.include_router(runtime_router)
    app.include_router(tools_router)
    app.include_router(metering_router)
    app.include_router(billing_router)
    app.include_router(observability_router)

    @app.on_event("startup")
    async def startup() -> None:
        engine = app.state.async_engine
        try:
            async with engine.begin() as conn:
                await conn.run_sync(lambda _: None)
        except Exception:
            pass

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await app.state.async_engine.dispose()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
