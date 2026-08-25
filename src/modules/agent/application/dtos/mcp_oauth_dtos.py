from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class McpOAuthStartInput(BaseModel):
    tool_id: UUID
    redirect_uri: str = Field(..., min_length=1)
    scopes: list[str] = Field(default_factory=list)
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    registration_endpoint: str | None = None
    authorization_server_issuer: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    timeout_ms: int = Field(default=30000, ge=1)


class McpOAuthStartOutput(BaseModel):
    authorization_url: str
    state: str
    status: str = "pending"


class McpOAuthCompleteInput(BaseModel):
    tool_id: UUID
    code: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    timeout_ms: int = Field(default=30000, ge=1)


class McpOAuthStatusInput(BaseModel):
    tool_id: UUID


class McpOAuthStatusOutput(BaseModel):
    status: str
    connected: bool
    authorization_server_issuer: str | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_at: str | None = None


class McpOAuthDisconnectInput(BaseModel):
    tool_id: UUID


class McpOAuthDisconnectOutput(BaseModel):
    status: str = "disconnected"


class McpOAuthDeviceStartInput(BaseModel):
    tool_id: Any
    scopes: list[str] = Field(default_factory=list)
    authorization_server_issuer: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    timeout_ms: int = Field(default=30000, ge=1)


class McpOAuthDeviceStartOutput(BaseModel):
    status: str = "device_pending"
    verification_uri: str
    verification_uri_complete: str | None = None
    user_code: str
    expires_in: int | None = None
    interval: int = 5
    authorization_server_issuer: str | None = None
    scopes: list[str] = Field(default_factory=list)


class McpOAuthDevicePollInput(BaseModel):
    tool_id: Any
    timeout_ms: int = Field(default=30000, ge=1)


class McpOAuthDevicePollOutput(BaseModel):
    status: str
    connected: bool = False
    authorization_server_issuer: str | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_at: str | None = None
    error: str | None = None
    interval: int | None = None
