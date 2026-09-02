from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SaveNetworkDraftInput(BaseModel):
    project_id: UUID
    network_id: UUID
    expected_revision: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)
    definition: dict[str, Any]
