from typing import Any

from pydantic import BaseModel, Field


class ResponseCookie(BaseModel):
    key: str
    value: str
    max_age: int | None = None
    httponly: bool = False
    secure: bool = False
    samesite: str = "lax"
    path: str = "/"


class DeleteResponseCookie(BaseModel):
    key: str
    httponly: bool = False
    secure: bool = False
    samesite: str = "lax"
    path: str = "/"


class Response(BaseModel):
    status_code: int = 200
    body: Any = None
    headers: dict[str, str] = Field(default_factory=dict)
    cookies: list[ResponseCookie] = Field(default_factory=list)
    delete_cookies: list[DeleteResponseCookie] = Field(default_factory=list)
