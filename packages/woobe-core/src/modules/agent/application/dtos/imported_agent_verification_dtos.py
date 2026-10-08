from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict


class VerifyImportedAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    agent_id: UUID
    draft_id: UUID
    lifecycle: Literal["draft", "staging", "release", "production"] = "draft"
    release_id: UUID | None = None
