from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class ProviderCredentialModel(BaseModel):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("project_id", "provider", "name"),
        {"schema": "ai"},
    )

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    provider: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    encrypted_secret: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)


class AgentModel(BaseModel):
    __tablename__ = "agents"
    __table_args__ = {"schema": "ai"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    provider_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.provider_credentials.id")
    )
    fallback_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.provider_credentials.id")
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(64))
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(255))
    fallback_provider: Mapped[str | None] = mapped_column(String(64))
    fallback_model: Mapped[str | None] = mapped_column(String(255))
    temperature: Mapped[float | None] = mapped_column(Float)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    session_mode: Mapped[str] = mapped_column(String(32), default="stateless")
    status: Mapped[str] = mapped_column(String(32), default="active")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class OutboxEventModel(BaseOutbox):
    __tablename__ = "outbox_events"
    __table_args__ = {"schema": "ai"}


class InboxEventModel(BaseInbox):
    __tablename__ = "inbox_events"
    __table_args__ = {"schema": "ai"}


class AgentPromptModel(BaseModel):
    __tablename__ = "agent_prompts"
    __table_args__ = {"schema": "ai"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("ai.agents.id"))
    version: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("identity.users.id"))


class AgentContractModel(BaseModel):
    __tablename__ = "agent_contracts"
    __table_args__ = {"schema": "ai"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("ai.agents.id"))
    version: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255), default="")
    input_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    validation_mode: Mapped[str] = mapped_column(String(16), default="loose")
    repair_attempts: Mapped[int] = mapped_column(Integer, default=0)
    additional_instructions: Mapped[str | None] = mapped_column(Text)
    schema_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="draft")


class AgentModelConfigModel(BaseModel):
    __tablename__ = "agent_model_configs"
    __table_args__ = {"schema": "ai"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("ai.agents.id"))
    version: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(64))
    provider_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.provider_credentials.id")
    )
    model: Mapped[str] = mapped_column(String(255))
    base_url: Mapped[str | None] = mapped_column(String(512))
    temperature: Mapped[float | None] = mapped_column(Float)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    session_mode: Mapped[str | None] = mapped_column(String(32))
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="draft")


class AgentReleaseModel(BaseModel):
    __tablename__ = "agent_releases"
    __table_args__ = {"schema": "ai"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("ai.agents.id"))
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    prompt_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.agent_prompts.id")
    )
    contract_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.agent_contracts.id")
    )
    knowledge_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge.knowledge_versions.id")
    )
    model_config_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.agent_model_configs.id")
    )
    # Snapshot fields — complete agent config inline
    name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    response_format: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(255))
    provider_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.provider_credentials.id")
    )
    fallback_provider: Mapped[str | None] = mapped_column(String(64))
    fallback_model: Mapped[str | None] = mapped_column(String(255))
    fallback_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.provider_credentials.id")
    )
    base_url: Mapped[str | None] = mapped_column(String(512))
    temperature: Mapped[float | None] = mapped_column(Float)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    session_mode: Mapped[str | None] = mapped_column(String(32))
    agent_status: Mapped[str | None] = mapped_column(String(32))
    collection_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PG_UUID))
    runtime_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Meta
    release_notes: Mapped[str | None] = mapped_column(Text)
    risk_score: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("identity.users.id"))
    promoted_by: Mapped[UUID | None] = mapped_column(ForeignKey("identity.users.id"))
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentReleaseTestModel(BaseModel):
    __tablename__ = "agent_release_tests"
    __table_args__ = {"schema": "ai"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("ai.agents.id"))
    release_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.agent_releases.id")
    )
    contract_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.agent_contracts.id")
    )
    input_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    expected_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    actual_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    validation_errors: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
