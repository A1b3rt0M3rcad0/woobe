from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from modules.network.domain.enums import NetworkEnvironment


class EnsureNetworkRequest(BaseModel):
    name: str = Field(default="Project Network", min_length=1, max_length=255)


class SaveNetworkDraftRequest(BaseModel):
    project_id: UUID
    expected_revision: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)
    definition: dict[str, Any]


class PromotionRequest(BaseModel):
    project_id: UUID
    environment: Literal[
        NetworkEnvironment.STAGING,
        NetworkEnvironment.PRODUCTION,
    ]
    expected_revision: int | None = Field(default=None, ge=0)
    expected_network_version_id: UUID | None = None
    approved_action_ids: list[str] = Field(default_factory=list, max_length=256)


class RollbackNetworkRequest(BaseModel):
    project_id: UUID
    target_version_id: UUID


class CreateNetworkSessionRequest(BaseModel):
    project_id: UUID
    environment: NetworkEnvironment
    title: str = Field(default="New Network session", max_length=255)
    external_session_id: str | None = Field(default=None, max_length=255)


class RunNetworkRequest(BaseModel):
    project_id: UUID
    network_session_id: UUID
    message: str = Field(min_length=1, max_length=32768)
    external_context: dict[str, Any] | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
    expected_draft_revision: int | None = Field(default=None, ge=0)