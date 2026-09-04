from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from shared.security.principal import SecurityPrincipal


class OperationOutcome(StrEnum):
    """Transport-neutral classification of an application operation result."""

    SUCCESS = "success"
    CREATED = "created"
    ACCEPTED = "accepted"
    INVALID = "invalid"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    UNPROCESSABLE = "unprocessable"
    FAILURE = "failure"
    NOT_IMPLEMENTED = "not_implemented"
    UPSTREAM_FAILURE = "upstream_failure"


class OperationRequest(BaseModel):
    """Input envelope used by synchronous module entrypoints.

    The envelope carries application data and an authenticated principal. HTTP
    concepts such as methods, URLs, cookies and headers are intentionally absent.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    principal: SecurityPrincipal | None = None
    body: Any = None
    query_params: dict[str, Any] = Field(default_factory=dict)
    path_params: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def query(self) -> dict[str, Any]:
        return self.query_params

    @property
    def params(self) -> dict[str, Any]:
        return self.path_params


class OperationResult(BaseModel):
    """Transport-neutral output envelope returned by module entrypoints."""

    outcome: OperationOutcome = OperationOutcome.SUCCESS
    body: Any = None
    metadata: dict[str, str] = Field(default_factory=dict)
