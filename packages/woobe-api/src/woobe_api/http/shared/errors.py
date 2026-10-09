import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

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
from shared.security.redaction import redact_text

logger = logging.getLogger(__name__)


async def authentication_handler(
    request: Request,
    exc: AuthenticationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"success": False, "message": str(exc), "data": None},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authorization_handler(
    request: Request,
    exc: AuthorizationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"success": False, "message": str(exc), "data": None},
    )


async def payload_too_large_handler(
    request: Request,
    exc: PayloadTooLargeError,
) -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={"success": False, "message": str(exc), "data": None},
    )


async def runtime_timeout_handler(
    request: Request,
    exc: RuntimeTimeoutError,
) -> JSONResponse:
    return JSONResponse(
        status_code=504,
        content={"success": False, "message": str(exc), "data": None},
    )


async def rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"success": False, "message": str(exc), "data": None},
        headers={"Retry-After": str(exc.retry_after)},
    )


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"success": False, "message": str(exc), "data": None},
    )


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"success": False, "message": str(exc), "data": None},
    )


async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    code = getattr(exc, "code", None)
    data = None
    if isinstance(code, str):
        data = {"code": code}
        for field_name in (
            "target_type",
            "target_id",
            "environment",
            "run_id",
            "status",
            "fields",
            "scope",
            "reason",
        ):
            value = getattr(exc, field_name, None)
            if value is not None:
                data[field_name] = value if isinstance(value, (list, dict)) else str(value)
    return JSONResponse(
        status_code=409,
        content={"success": False, "message": str(exc), "data": data},
    )


async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"success": False, "message": str(exc), "data": None},
    )


async def pydantic_validation_handler(
    request: Request,
    exc: PydanticValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation error",
            "data": exc.errors(),
        },
    )


async def request_validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    if request.url.path.startswith("/projects/") and "/asac/" in request.url.path:
        # Strict ASaC requests contain free-form author messages. Rejection must
        # not echo those messages, unknown fields or Pydantic input snapshots.
        return JSONResponse(status_code=422, content={"success": False,
            "message": "ASaC request does not match its advertised contract",
            "data": {"asac_schema_version": "1.0", "diagnostics": [{"code": "ASAC_REQUEST_INVALID"}]},
            "meta": {"complete": False}})
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Request validation error",
            "data": exc.errors(),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", redact_text(str(exc)))
    cors_origin = "*"
    try:
        settings = request.app.state.settings
        origins = settings.cors_origins.split(",")
        origin = request.headers.get("origin", "")
        cors_origin = origin if origin in origins else origins[0]
    except Exception:
        pass
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error", "data": None},
        headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Credentials": "true",
        },
    )



async def database_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # SQLAlchemy exception text can contain bound author content or protected
    # runtime data. Return only a reviewed fencing code, never SQL/parameters.
    origin=getattr(exc,"orig",None)
    for code in ("ASAC_LEASE_FENCED","ASAC_LEASE_EXPIRED","ASAC_DEPLOYMENT_COMMIT_INVALID","ASAC_DEPLOYMENT_RECEIPT_REQUIRED","ASAC_SELECTION_MANAGED","ASAC_PROJECT_MANAGED_LIFECYCLE_REQUIRED","ASAC_PROJECT_QUALIFIED_PUBLICATION_REQUIRED","ASAC_PROJECT_POLICY_RECEIPT_REQUIRED","ASAC_PROJECT_POLICY_STALE","ASAC_PROJECT_POLICY_IMMUTABLE","ASAC_PROJECT_PRODUCTION_ACTOR_REQUIRED"):
        if code in str(origin):
            logger.info("Database rejected workflow lease: %s",code)
            return JSONResponse(status_code=409,content={"success":False,
                "message":"Database rejected an incompatible lifecycle transaction",
                "data":{"asac_schema_version":"1.0","diagnostics":[{"code":code}]},
                "meta":{"complete":False}})
    cause = getattr(origin, "__cause__", None)
    logger.error("Unhandled database exception (%s), sqlstate=%s, constraint=%s",
        type(exc).__name__, getattr(origin, "sqlstate", None), getattr(cause, "constraint_name", None))
    return JSONResponse(status_code=500,content={"success":False,
        "message":"Internal server error","data":None})
