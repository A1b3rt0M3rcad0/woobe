import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from shared.infra.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

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
    return JSONResponse(
        status_code=409,
        content={"success": False, "message": str(exc), "data": None},
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
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Request validation error",
            "data": exc.errors(),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
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
