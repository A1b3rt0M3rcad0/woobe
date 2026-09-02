from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from modules.network.domain.enums import NetworkEnvironment


class PreviewNetworkPromotionInput(BaseModel):
    project_id: UUID
    network_id: UUID
    environment: NetworkEnvironment


class PromoteNetworkInput(BaseModel):
    project_id: UUID
    network_id: UUID
    environment: NetworkEnvironment
    created_by: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=0)
    expected_network_version_id: UUID | None = None
    approved_action_ids: list[str] = Field(default_factory=list, max_length=256)


class CreateNetworkPromotionVersionInput(BaseModel):
    network_id: UUID
    project_id: UUID
    kind: str
    version: str
    definition: dict[str, Any]
    resolved_bindings: dict[str, Any]
    composition_hash: str
    created_by: UUID | None = None
    source_draft_revision: int | None = None
    source_staging_version_id: UUID | None = None
    entry_agent_id: UUID | None = None
    entry_agent_release_id: UUID | None = None
    entry_agent_release_version: str | None = None
    public_output_contract: dict[str, Any] | None = None
    public_output_contract_hash: str | None = None
    agent_release_manifest: list[dict[str, Any]] = Field(default_factory=list)
    agent_release_manifest_hash: str | None = None
    runtime_settings_hash: str | None = None
    release_fingerprint: str | None = None
    change_kind: str | None = None
    activation_kind: str | None = None
    change_description: str | None = None
