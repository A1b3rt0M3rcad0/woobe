from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class McpOAuthInput(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)


class McpOAuthStartInput(McpOAuthInput):
    tool_id: UUID
    redirect_uri: str = Field(..., min_length=1)
    scopes: list[str] = Field(default_factory=list)
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    registration_endpoint: str | None = None
    authorization_server_issuer: str | None = None
    client_id: str | None = None
    client_secret: str | None = Field(default=None, repr=False, json_schema_extra={'writeOnly': True})
    timeout_ms: int = Field(default=30000, ge=1)


class McpOAuthStartOutput(BaseModel):
    authorization_url: str
    state: str
    status: str = "pending"


class McpOAuthCompleteInput(McpOAuthInput):
    tool_id: UUID
    code: str = Field(..., min_length=1, repr=False, json_schema_extra={'writeOnly': True})
    state: str = Field(..., min_length=1, repr=False, json_schema_extra={'writeOnly': True})
    timeout_ms: int = Field(default=30000, ge=1)


class McpOAuthStatusInput(McpOAuthInput):
    tool_id: UUID


class McpOAuthStatusOutput(BaseModel):
    status: str
    connected: bool
    authorization_server_issuer: str | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_at: str | None = None


class McpOAuthDisconnectInput(McpOAuthInput):
    tool_id: UUID


class McpOAuthDisconnectOutput(BaseModel):
    status: str = "disconnected"


class McpOAuthDeviceStartInput(McpOAuthInput):
    tool_id: UUID
    scopes: list[str] = Field(default_factory=list)
    authorization_server_issuer: str | None = None
    client_id: str | None = None
    client_secret: str | None = Field(default=None, repr=False, json_schema_extra={'writeOnly': True})
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


class McpOAuthDevicePollInput(McpOAuthInput):
    tool_id: UUID
    timeout_ms: int = Field(default=30000, ge=1)


class McpOAuthDevicePollOutput(BaseModel):
    status: str
    connected: bool = False
    authorization_server_issuer: str | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_at: str | None = None
    error: str | None = None
    interval: int | None = None
