from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImportedNetworkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    action: Literal[
        "prepare_network",
        "save_network_draft",
        "create_staging",
        "create_immutable_release",
        "activate_production",
        "verify_materialized_package",
    ]
    network_id: UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    expected_revision: int | None = None
    source_version_id: UUID | None = None
    release_notes: str | None = None
    activation_reason: str | None = None
    lifecycle: Literal["draft", "staging", "release", "production"] = "draft"
    portable_spec: dict[str, Any] | None = None
    agents: dict[str, UUID] = Field(default_factory=dict)
    snapshots: dict[str, dict[str, str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def phase_requirements(self):
        if self.action != "prepare_network" and self.network_id is None:
            raise ValueError("Network identity is required")
        if (
            self.action in {"save_network_draft", "verify_materialized_package"}
            and self.portable_spec is None
        ):
            raise ValueError("Approved graph is required")
        if (
            self.action
            in {"save_network_draft", "create_staging", "verify_materialized_package"}
            and self.expected_revision is None
        ):
            raise ValueError("Approved Draft revision is required")
        if (
            self.action in {"create_immutable_release", "activate_production"}
            and self.source_version_id is None
        ):
            raise ValueError("Immutable source identity is required")
        if self.action == "create_immutable_release" and not (
            self.release_notes and len(self.release_notes.strip()) >= 3
        ):
            raise ValueError("Release description is required")
        if self.action == "activate_production" and not (
            self.activation_reason and len(self.activation_reason.strip()) >= 3
        ):
            raise ValueError("Production activation reason is required")
        return self
