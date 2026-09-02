from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ListManagedNetworkVersionsInput(BaseModel):
    network_id: UUID
    project_id: UUID


class ListNetworkActivationsInput(BaseModel):
    network_id: UUID
    project_id: UUID


class GetNetworkExecutionSnapshotInput(BaseModel):
    execution_id: UUID
    project_id: UUID


class ActivateNetworkProductionInput(BaseModel):
    network_id: UUID
    project_id: UUID
    source_version_id: UUID
    expected_current_production_version_id: UUID | None = None
    change_description: str = Field(min_length=3, max_length=2000)
    created_by: UUID | None = None


class ManagedNetworkVersion(BaseModel):
    id: UUID
    network_id: UUID
    project_id: UUID
    kind: str
    version: str
    composition_hash: str
    definition: dict[str, Any]
    resolved_bindings: dict[str, Any]
    created_at: datetime | None = None
    created_by: UUID | None = None
    source_version_id: UUID | None = None
    activation_kind: str | None = None
    change_description: str | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)


class NetworkProductionActivation(BaseModel):
    id: UUID
    network_id: UUID
    version_id: UUID
    previous_version_id: UUID | None = None
    activation_kind: str
    change_description: str
    created_by: UUID | None = None
    created_at: datetime | None = None


class NetworkProductionState(BaseModel):
    network_id: UUID
    project_id: UUID
    production_version_id: UUID | None = None


class ActivateNetworkProductionOutput(BaseModel):
    version: ManagedNetworkVersion
    activation: NetworkProductionActivation
