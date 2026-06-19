import logging
from typing import cast

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.types import ExceptionHandler

from modules.agent.presentation.routes import agent_router
from modules.agent.presentation.routes import router as agent_ai_router
from modules.agent.presentation.routes import knowledge_router as agent_knowledge_router
from modules.agent.presentation.routes import runtime_router as agent_runtime_router
from modules.billing.presentation.routes import router as billing_router
from modules.core.presentation.routes import router as core_router
from modules.identity.presentation.routes import router as identity_router
from modules.metering.presentation.routes import router as metering_router
from modules.observability.presentation.routes import router as observability_router
from modules.agent.presentation.routes import tools_router
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from shared.presentation.errors import (
    authentication_handler,
    conflict_handler,
    domain_error_handler,
    not_found_handler,
    pydantic_validation_handler,
    rate_limit_handler,
    request_validation_handler,
    unhandled_exception_handler,
    validation_handler,
)
from shared.security.access_tokens import AccessTokenCodec
from shared.security.dependency import enforce_request_security
from shared.security.http_guard import HttpSecurityGuard
from shared.security.rate_limit import LoginRateLimiter

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = Settings.model_validate({})

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logger.info("Logging configured at level %s", settings.log_level)

    app = FastAPI(
        title="ProjectRAI",
        description="Runtime AI Platform - Production-ready AI agent runtime",
        version="0.1.0",
    )

    app.state.settings = settings
    app.state.async_engine = create_engine(settings)
    app.state.session_factory = create_session_factory(app.state.async_engine)
    app.state.access_token_codec = AccessTokenCodec(
        signing_key=settings.secret_key,
        issuer=settings.auth_issuer,
        audience=settings.auth_audience,
        ttl_seconds=settings.access_token_ttl_seconds,
        leeway_seconds=settings.auth_clock_skew_seconds,
    )
    app.state.security_guard = HttpSecurityGuard(
        session_factory=app.state.session_factory,
        token_codec=app.state.access_token_codec,
        login_rate_limiter=LoginRateLimiter(
            max_attempts=settings.login_rate_limit_attempts,
            window_seconds=settings.login_rate_limit_window_seconds,
        ),
    )

    cors_origins = settings.cors_origins.split(",")
    logger.info("CORS allowed origins: %s", cors_origins)

    @app.middleware("http")
    async def cors_safe_guard(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled error processing %s %s",
                request.method,
                request.url.path,
            )
            origin = request.headers.get("origin", "")
            cors_origin = (
                origin
                if origin in cors_origins
                else cors_origins[0]
                if cors_origins
                else "*"
            )
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Internal server error",
                    "data": None,
                },
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

    app.add_exception_handler(
        AuthenticationError,
        cast(ExceptionHandler, authentication_handler),
    )
    app.add_exception_handler(RateLimitError, cast(ExceptionHandler, rate_limit_handler))
    app.add_exception_handler(DomainError, cast(ExceptionHandler, domain_error_handler))
    app.add_exception_handler(NotFoundError, cast(ExceptionHandler, not_found_handler))
    app.add_exception_handler(ConflictError, cast(ExceptionHandler, conflict_handler))
    app.add_exception_handler(ValidationError, cast(ExceptionHandler, validation_handler))
    app.add_exception_handler(
        PydanticValidationError,
        cast(ExceptionHandler, pydantic_validation_handler),
    )
    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, request_validation_handler),
    )
    app.add_exception_handler(
        Exception,
        cast(ExceptionHandler, unhandled_exception_handler),
    )

    protected_dependencies = [Depends(enforce_request_security)]
    app.include_router(identity_router, dependencies=protected_dependencies)
    app.include_router(core_router, dependencies=protected_dependencies)
    app.include_router(agent_router, dependencies=protected_dependencies)
    app.include_router(agent_ai_router, dependencies=protected_dependencies)
    app.include_router(agent_knowledge_router, dependencies=protected_dependencies)
    app.include_router(agent_runtime_router, dependencies=protected_dependencies)
    app.include_router(tools_router, dependencies=protected_dependencies)
    app.include_router(metering_router, dependencies=protected_dependencies)
    app.include_router(billing_router, dependencies=protected_dependencies)
    app.include_router(observability_router, dependencies=protected_dependencies)

    @app.on_event("startup")
    async def startup() -> None:
        engine = app.state.async_engine
        async with engine.begin() as conn:
            await conn.run_sync(lambda _: None)
        logger.info("API runtime started without background workers")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await app.state.async_engine.dispose()
        logger.info("API runtime stopped")

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "runtime": "api",
        }

    return app


app = create_app()
