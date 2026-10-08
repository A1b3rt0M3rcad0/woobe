from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateImportedEnvironmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    key: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=128)
    kind: Literal["value", "secret"]
    value: str = Field(min_length=1)
