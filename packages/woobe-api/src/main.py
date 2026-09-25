import asyncio
import logging
from contextlib import asynccontextmanager
from typing import cast

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ExceptionHandler

from chat_runtime_composition import ApiChatRuntimeGateway
from modules.agent.entrypoint import (
    SETTINGS,
    build_http_tool_executor,
    close_http_tool_executor,
)
from modules.identity.entrypoint import build_access_token_codec
from public_runtime_routes import router as public_runtime_router
from shared.composition_resources import DATABASE_ENGINE, EXECUTION_STATE_STORE
from shared.infra.database.session import create_session_factory
from shared.infra.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PayloadTooLargeError,
    RateLimitError,
    RuntimeTimeoutError,
    ValidationError,
)
from shared.infra.security import SqlSecurityAuthenticator
from shared.observability.logging_config import configure_logging
from shared.security.rate_limit import (
    ApiKeyConcurrencyLimiter,
    ApiKeyRequestLimiter,
    LoginRateLimiter,
)
from woobe_api.http.agent import HTTP_ROUTERS as AGENT_HTTP_ROUTERS
from woobe_api.http.chat_surface.reattach_routes import (
    router as chat_surface_reattach_router,
)
from woobe_api.http.chat_surface.routes import router as chat_surface_router
from woobe_api.http.core.routes import router as core_router
from woobe_api.http.identity.instance_routes import router as instance_router
from woobe_api.http.identity.routes import router as identity_router
from woobe_api.http.metering.routes import router as metering_router
from woobe_api.http.network.routes import router as network_router
from woobe_api.http.observability.routes import router as observability_router
from woobe_api.http.shared.errors import (
    authentication_handler,
    authorization_handler,
    conflict_handler,
    domain_error_handler,
    not_found_handler,
    payload_too_large_handler,
    pydantic_validation_handler,
    rate_limit_handler,
    request_validation_handler,
    runtime_timeout_handler,
    unhandled_exception_handler,
    validation_handler,
)
from woobe_api.http.shared.runtime_environment_routes import (
    router as runtime_environment_router,
)
from woobe_api.middleware.observability import RequestObservabilityMiddleware
from woobe_api.security.dependency import enforce_request_security
from woobe_api.security.http_guard import HttpSecurityGuard

logger = logging.getLogger(__name__)


def _csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def create_app() -> FastAPI:
    settings = SETTINGS
    configure_logging(level=settings.log_level, json_logs=settings.json_logs)
    logger.info(
        "Application configuration loaded",
        extra={
            "environment": settings.environment,
            "edition": settings.edition,
            "service_role": settings.service_role,
        },
    )

    @asynccontextmanager
    async def lifespan(runtime_app: FastAPI):
        engine = runtime_app.state.async_engine
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Woobe API runtime started without background workers")
        try:
            yield
        finally:
            await close_http_tool_executor()
            await runtime_app.state.async_engine.dispose()
            logger.info("Woobe API runtime stopped")

    app = FastAPI(
        title="Woobe",
        description="Control plane and runtime for versioned AI products",
        version="0.14.0",
        lifespan=lifespan,
    )

    security_session_factory = create_session_factory(DATABASE_ENGINE)
    app.state.settings = settings
    app.state.async_engine = DATABASE_ENGINE
    app.state.execution_state_store = EXECUTION_STATE_STORE
    app.state.access_token_codec = build_access_token_codec()
    app.state.http_tool_executor = build_http_tool_executor()
    app.state.chat_surface_runtime_gateway = ApiChatRuntimeGateway(
        settings=settings,
        app_state=app.state,
    )
    api_key_rate_limiter = ApiKeyRequestLimiter(
        max_requests=settings.api_key_rate_limit_requests,
        window_seconds=settings.api_key_rate_limit_window_seconds,
        session_factory=security_session_factory,
    )
    app.state.security_guard = HttpSecurityGuard(
        authenticator=SqlSecurityAuthenticator(
            session_factory=security_session_factory,
            token_codec=app.state.access_token_codec,
            api_key_rate_limiter=api_key_rate_limiter,
        ),
        login_rate_limiter=LoginRateLimiter(
            max_attempts=settings.login_rate_limit_attempts,
            window_seconds=settings.login_rate_limit_window_seconds,
            session_factory=security_session_factory,
        ),
        api_key_concurrency_limiter=ApiKeyConcurrencyLimiter(
            max_concurrency=settings.runtime_max_concurrency_per_key,
            session_factory=security_session_factory,
        ),
        settings=settings,
    )

    cors_origins = _csv_values(settings.cors_origins)
    trusted_hosts = _csv_values(settings.trusted_hosts)
    logger.info(
        "HTTP boundary configured",
        extra={
            "cors_origin_count": len(cors_origins),
            "trusted_host_count": len(trusted_hosts),
            "request_max_bytes": settings.request_max_bytes,
        },
    )

    app.add_middleware(
        RequestObservabilityMiddleware,
        max_request_bytes=settings.request_max_bytes,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

    @app.middleware("http")
    async def cors_safe_guard(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled error processing request",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                },
            )
            origin = request.headers.get("origin", "")
            cors_origin = origin if origin in cors_origins else ""
            headers = {}
            if cors_origin:
                headers = {
                    "Access-Control-Allow-Origin": cors_origin,
                    "Access-Control-Allow-Credentials": "true",
                }
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Internal server error",
                    "data": None,
                },
                headers=headers,
            )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-API-Key",
            "X-CSRF-Token",
            "X-Request-ID",
            "X-Correlation-ID",
            "Last-Event-ID",
            "Idempotency-Key",
            "X-Woobe-Host-Origin",
        ],
        expose_headers=[
            "X-Request-ID",
            "X-Correlation-ID",
            "X-Network-Execution-ID",
            "X-Woobe-Message-Request-ID",
            "X-Woobe-Run-ID",
        ],
    )

    app.add_exception_handler(
        AuthenticationError,
        cast(ExceptionHandler, authentication_handler),
    )
    app.add_exception_handler(
        AuthorizationError,
        cast(ExceptionHandler, authorization_handler),
    )
    app.add_exception_handler(
        PayloadTooLargeError,
        cast(ExceptionHandler, payload_too_large_handler),
    )
    app.add_exception_handler(
        RuntimeTimeoutError,
        cast(ExceptionHandler, runtime_timeout_handler),
    )
    app.add_exception_handler(
        RateLimitError, cast(ExceptionHandler, rate_limit_handler)
    )
    app.add_exception_handler(DomainError, cast(ExceptionHandler, domain_error_handler))
    app.add_exception_handler(NotFoundError, cast(ExceptionHandler, not_found_handler))
    app.add_exception_handler(ConflictError, cast(ExceptionHandler, conflict_handler))
    app.add_exception_handler(
        ValidationError, cast(ExceptionHandler, validation_handler)
    )
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

    app.include_router(instance_router)

    security_dependency = Depends(enforce_request_security)
    app.router.dependencies.append(security_dependency)
    try:
        app.include_router(identity_router)
        app.include_router(core_router)
        app.include_router(chat_surface_router)
        app.include_router(chat_surface_reattach_router)
        app.include_router(public_runtime_router)
        for agent_http_router in AGENT_HTTP_ROUTERS:
            app.include_router(agent_http_router)
        app.include_router(runtime_environment_router)
        app.include_router(metering_router)
        app.include_router(observability_router)
        app.include_router(network_router)
    finally:
        app.router.dependencies.remove(security_dependency)

    @app.get("/live", include_in_schema=False)
    async def live():
        return {"status": "ok", "runtime": "api", "product": "woobe"}

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "ok"}

    @app.get("/ready", include_in_schema=False)
    async def ready():
        try:
            async with asyncio.timeout(settings.readiness_timeout_seconds):
                async with app.state.async_engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "unavailable", "dependency": "database"},
            )
        return {"status": "ok", "dependency": "database"}

    return app


app = create_app()


async def _main() -> None:
    await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(_main())
