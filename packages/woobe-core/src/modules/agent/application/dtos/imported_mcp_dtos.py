from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class CommitImportedMcpInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    tool_id: UUID
    expected_revision: str
    config: dict
    status: Literal["ready", "oauth_required"]
    discovered_count: int = Field(ge=0)
    require_ready: bool = False
