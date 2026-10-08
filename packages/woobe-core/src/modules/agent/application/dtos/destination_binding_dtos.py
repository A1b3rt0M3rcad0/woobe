from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from modules.agent.domain.enums import Provider
from modules.agent.application.dtos.portable_credential_metadata import (
    PortableCredentialMetadata,
)


class CredentialInspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Provider
    metadata: PortableCredentialMetadata | None = None
    credential_id: UUID | None = None
    protected_ref: str | None = None


class EnvironmentInspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    existing_key: str | None = None
    protected_ref: str | None = None
    kind: Literal["value", "secret"] | None = None


class KnowledgeInspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vector_snapshot_id: UUID


class InspectDestinationBindingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    credentials: dict[str, CredentialInspectionInput] = Field(default_factory=dict)
    project_environment: dict[str, EnvironmentInspectionInput] = Field(
        default_factory=dict
    )
    secrets: dict[str, EnvironmentInspectionInput] = Field(default_factory=dict)
    knowledge: dict[str, KnowledgeInspectionInput] = Field(default_factory=dict)
