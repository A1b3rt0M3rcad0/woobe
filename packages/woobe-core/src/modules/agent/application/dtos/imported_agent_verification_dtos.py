from uuid import UUID
from pydantic import BaseModel, ConfigDict


class VerifyImportedAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    agent_id: UUID
    draft_id: UUID
