import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from modules.ai.presentation.routes import router as ai_router
from modules.billing.presentation.routes import router as billing_router
from modules.core.presentation.routes import router as core_router
from modules.identity.presentation.routes import router as identity_router
from modules.knowledge.presentation.routes import router as knowledge_router
from modules.metering.presentation.routes import router as metering_router
from modules.observability.presentation.routes import router as observability_router
from modules.runtime.presentation.routes import router as runtime_router
from modules.tools.presentation.routes import router as tools_router
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.presentation.errors import (
    conflict_handler,
    domain_error_handler,
    not_found_handler,
    pydantic_validation_handler,
    request_validation_handler,
    unhandled_exception_handler,
    validation_handler,
)
from shared.domain.errors import ConflictError, DomainError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = Settings()

    app = FastAPI(
        title="ProjectRAI",
        description="Runtime AI Platform \u2014 Production-ready AI agent runtime",
        version="0.1.0",
    )

    app.state.settings = settings
    app.state.async_engine = create_engine(settings)
    app.state.session_factory = create_session_factory(app.state.async_engine)

    cors_origins = settings.cors_origins.split(",")
    logger.info("CORS allowed origins: %s", cors_origins)

    @app.middleware("http")
    async def cors_safe_guard(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            logger.exception("Unhandled error processing %s %s", request.method, request.url.path)
            origin = request.headers.get("origin", "")
            cors_origin = origin if origin in cors_origins else cors_origins[0] if cors_origins else "*"
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"Internal server error: {exc}", "data": None},
                headers={
                    "Access-Control-Allow-Origin": cors_origin,
                    "Access-Control-Allow-Credentials": "true",
                },
            )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(ConflictError, conflict_handler)
    app.add_exception_handler(ValidationError, validation_handler)
    app.add_exception_handler(PydanticValidationError, pydantic_validation_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

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
