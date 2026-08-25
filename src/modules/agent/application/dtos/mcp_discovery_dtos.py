from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


def _default_mcp_permission() -> dict[str, Any]:
    return {"mode": "review", "risk_level": "unknown"}


class McpDiscoverInput(BaseModel):
    server_url: str = Field(..., min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_ms: int = Field(default=30000, ge=1)


class McpDiscoveredTool(BaseModel):
    name: str
    title: str | None = None
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    permission: dict[str, Any] = Field(default_factory=_default_mcp_permission)


class McpDiscoverOutput(BaseModel):
    tools: list[McpDiscoveredTool]
    initialized: bool = False
    error: str | None = None
    phase: str | None = None
    http_status: int | None = None
    www_authenticate: str | None = None
