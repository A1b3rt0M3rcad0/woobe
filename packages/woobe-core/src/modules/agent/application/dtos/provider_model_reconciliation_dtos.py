"""Typed requests for explicit provider catalog reconciliation."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReconciliationScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    provider_credential_id: UUID
    environment: Literal["draft", "staging", "production"] = "draft"
    capability: Literal["generation", "embedding"] | None = None


class ReconciliationSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str
    installed_model_id: UUID | None = None
    expected_model_revision: str | None = None
    candidate_digest: str


class ApplyProviderModelReconciliationInput(ReconciliationScope):
    expected_credential_revision: int = Field(ge=1)
    expected_configuration_revision: str | None = None
    selections: list[ReconciliationSelection] = Field(min_length=1, max_length=100)
