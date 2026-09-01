from uuid import UUID

from pydantic import BaseModel, Field


class RefreshMcpProviderToolsInput(BaseModel):
    tool_id: UUID
    timeout_ms: int = Field(default=30000, ge=1)


class RefreshMcpProviderToolsOutput(BaseModel):
    tool_id: UUID
    discovered_count: int
    initialized: bool
    status: str
    error: str | None = None
    http_status: int | None = None
    phase: str | None = None
