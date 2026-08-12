import asyncio
import logging
from typing import cast

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ExceptionHandler

from modules.agent.infra.adapters.http_tool_runtime import (
    close_http_tool_executor,
    configure_http_tool_executor,
)
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.presentation.credential_routes import router as credential_router
from modules.agent.presentation.mcp_tools_routes import router as mcp_tools_router
from modules.agent.presentation.public_runtime_routes import router as public_runtime_router
from modules.agent.presentation.release_activation_routes import router as release_activation_router
from modules.agent.presentation.routes import agent_router
from modules.agent.presentation.routes import router as agent_ai_router
from modules.agent.presentation.routes import knowledge_router as agent_knowledge_router
from modules.agent.presentation.routes import runtime_router as agent_runtime_router
from modules.agent.presentation.routes import tools_router
from modules.agent.presentation.tool_lifecycle_routes import router as tool_lifecycle_router
from modules.agent.presentation.vector_snapshot_routes import router as vector_snapshot_router
from modules.billing.presentation.routes import router as billing_router
from modules.chat_surface.presentation.routes import router as chat_surface_router
from modules.chat_surface.security import ChatSessionTokenCodec
from modules.core.presentation.routes import router as core_router
from modules.identity.presentation.routes import router as identity_router
from modules.metering.presentation.routes import router as metering_router
from modules.network.presentation import router as network_router
from modules.observability.presentation.routes import router as observability_router
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
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
from shared.observability.http import RequestObservabilityMiddleware
from shared.observability.logging_config import configure_logging
from shared.presentation.errors import (
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
from shared.runtime_environment_routes import router as runtime_environment_router
from shared.security.access_tokens import AccessTokenCodec
from shared.security.dependency import enforce_request_security
from shared.security.http_guard import HttpSecurityGuard
from shared.security.rate_limit import (
    ApiKeyConcurrencyLimiter,
    ApiKeyRequestLimiter,
    LoginRateLimiter,
)

logger = logging.getLogger(__name__)


def _csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def create_app() -> FastAPI:
    settings = Settings(service_role="api")
    configure_logging(level=settings.log_level, json_logs=settings.json_logs)
    logger.info(
        "Application configuration loaded",
        extra={
            "environment": settings.environment,
            "edition": settings.edition,
            "service_role": settings.service_role,
        },
    )

    app = FastAPI(
        title="Woobe",
        description="Control plane and runtime for versioned AI products",
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
    app.state.chat_session_token_codec = ChatSessionTokenCodec(
        signing_key=settings.chat_token_signing_key or settings.secret_key,
        issuer=settings.chat_token_issuer,
        audience=settings.chat_token_audience,
        ttl_seconds=settings.chat_token_ttl_seconds,
        leeway_seconds=settings.auth_clock_skew_seconds,
    )
    app.state.http_tool_executor = HttpToolExecutor(
        default_timeout_ms=settings.http_tool_timeout_max_ms,
        max_timeout_ms=settings.http_tool_timeout_max_ms,
        max_response_bytes=settings.http_tool_response_max_bytes,
    )
    configure_http_tool_executor(app.state.http_tool_executor)
    app.state.security_guard = HttpSecurityGuard(
        session_factory=app.state.session_factory,
        token_codec=app.state.access_token_codec,
        login_rate_limiter=LoginRateLimiter(
            max_attempts=settings.login_rate_limit_attempts,
            window_seconds=settings.login_rate_limit_window_seconds,
        ),
        api_key_rate_limiter=ApiKeyRequestLimiter(
            max_requests=settings.api_key_rate_limit_requests,
            window_seconds=settings.api_key_rate_limit_window_seconds,
        ),
        api_key_concurrency_limiter=ApiKeyConcurrencyLimiter(
            max_concurrency=settings.runtime_max_concurrency_per_key,
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

    security_dependency = Depends(enforce_request_security)
    app.router.dependencies.append(security_dependency)
    try:
        app.include_router(identity_router)
        app.include_router(core_router)
        app.include_router(chat_surface_router)
        app.include_router(public_runtime_router)
        app.include_router(credential_router)
        app.include_router(runtime_environment_router)
        app.include_router(release_activation_router)
        app.include_router(agent_router)
        app.include_router(agent_ai_router)
        app.include_router(agent_knowledge_router)
        app.include_router(vector_snapshot_router)
        app.include_router(agent_runtime_router)
        app.include_router(tools_router)
        app.include_router(tool_lifecycle_router)
        app.include_router(mcp_tools_router)
        app.include_router(metering_router)
        if settings.managed_billing_enabled:
            app.include_router(billing_router)
        app.include_router(observability_router)
        app.include_router(network_router)
    finally:
        app.router.dependencies.remove(security_dependency)

    @app.on_event("startup")
    async def startup() -> None:
        engine = app.state.async_engine
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Woobe API runtime started without background workers")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await close_http_tool_executor()
        await app.state.async_engine.dispose()
        logger.info("Woobe API runtime stopped")

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
