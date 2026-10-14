from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class PrepareVectorSnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    snapshot_id: UUID
    expected_build_config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    environment: Literal["draft", "staging", "production"] = "draft"
