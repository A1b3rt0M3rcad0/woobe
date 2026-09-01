from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def ok(data: Any = None, message: str = "ok") -> JSONResponse:
    return JSONResponse(content=jsonable_encoder({"success": True, "message": message, "data": data}))


def created(data: Any = None, message: str = "created") -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder({"success": True, "message": message, "data": data}),
        status_code=201,
    )


def error(message: str, status_code: int = 400, data: Any = None) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder({"success": False, "message": message, "data": data}),
        status_code=status_code,
    )
