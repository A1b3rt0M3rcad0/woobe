from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel


class ProviderCredentialModel(BaseModel):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("project_id", "provider", "name"),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    provider: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    encrypted_secret: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )


class AgentModel(BaseModel):
    __tablename__ = "agents"
    __table_args__ = {"schema": "agent"}

    project_id: Mapped[UUID]
    provider_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.provider_credentials.id")
    )
    fallback_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.provider_credentials.id")
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(64))
    behavior_spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(255))
    fallback_provider: Mapped[str | None] = mapped_column(String(64))
    fallback_model: Mapped[str | None] = mapped_column(String(255))
    temperature: Mapped[float | None] = mapped_column(Float)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    session_mode: Mapped[str] = mapped_column(String(32), default="stateful")
    status: Mapped[str] = mapped_column(String(32), default="active")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class AgentRuntimeEnvironmentStateModel(BaseModel):
    __tablename__ = "agent_runtime_environment_states"
    __table_args__ = (
        CheckConstraint(
            "environment IN ('draft', 'staging', 'production')",
            name="ck_agent_runtime_environment_states_environment",
        ),
        UniqueConstraint(
            "agent_id",
            "environment",
            name="uq_agent_runtime_environment_states_target_environment",
        ),
        Index(
            "ix_agent_runtime_environment_states_project_environment",
            "project_id",
            "environment",
        ),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent.agents.id", ondelete="CASCADE")
    )
    environment: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
    )
    external_context_values: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    updated_by: Mapped[UUID | None] = mapped_column(nullable=True)


class AgentPromptModel(BaseModel):
    __tablename__ = "agent_prompts"
    __table_args__ = (
        Index("ix_agent_prompts_agent_version", "agent_id", "version", unique=True),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.agents.id"))
    version: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_by: Mapped[UUID | None]


class AgentContractModel(BaseModel):
    __tablename__ = "agent_contracts"
    __table_args__ = (
        Index("ix_agent_contracts_agent_version", "agent_id", "version", unique=True),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.agents.id"))
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
    __table_args__ = (
        Index(
            "ix_agent_model_configs_agent_version", "agent_id", "version", unique=True
        ),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.agents.id"))
    version: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(64))
    provider_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.provider_credentials.id")
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
    __table_args__ = (
        Index("ix_agent_releases_agent_version", "agent_id", "version", unique=True),
        Index("ix_agent_releases_agent_status", "agent_id", "status"),
        CheckConstraint(
            "session_mode IN ('stateful', 'stateless')",
            name="ck_agent_releases_session_mode",
        ),
        Index(
            "uq_agent_releases_staging",
            "agent_id",
            unique=True,
            postgresql_where=text("status = 'staging'"),
        ),
        Index(
            "uq_agent_releases_production",
            "agent_id",
            unique=True,
            postgresql_where=text("status = 'production'"),
        ),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.agents.id"))
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    snapshot_kind: Mapped[str] = mapped_column(String(16), default="draft")
    prompt_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.agent_prompts.id")
    )
    contract_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.agent_contracts.id")
    )
    knowledge_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.knowledge_versions.id")
    )
    model_config_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.agent_model_configs.id")
    )
    name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    behavior_spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    response_format: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    external_context_contract: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(255))
    provider_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.provider_credentials.id")
    )
    fallback_provider: Mapped[str | None] = mapped_column(String(64))
    fallback_model: Mapped[str | None] = mapped_column(String(255))
    fallback_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.provider_credentials.id")
    )
    base_url: Mapped[str | None] = mapped_column(String(512))
    temperature: Mapped[float | None] = mapped_column(Float)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    session_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_status: Mapped[str | None] = mapped_column(String(32))
    collection_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PG_UUID))
    runtime_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    release_notes: Mapped[str | None] = mapped_column(Text)
    risk_score: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[UUID | None]
    promoted_by: Mapped[UUID | None]
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentReleaseTestModel(BaseModel):
    __tablename__ = "agent_release_tests"
    __table_args__ = {"schema": "agent"}

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.agents.id"))
    release_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.agent_releases.id")
    )
    contract_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.agent_contracts.id")
    )
    input_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    expected_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    actual_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    validation_errors: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)


class DocumentCollectionModel(BaseModel):
    __tablename__ = "document_collections"
    __table_args__ = {"schema": "agent"}

    project_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")


class AgentCollectionModel(BaseModel):
    __tablename__ = "agent_collections"
    __table_args__ = (
        UniqueConstraint("agent_id", "collection_id"),
        {"schema": "agent"},
    )

    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.agents.id"))
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent.document_collections.id")
    )


class DocumentModel(BaseModel):
    __tablename__ = "documents"
    __table_args__ = {"schema": "agent"}

    project_id: Mapped[UUID]
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent.document_collections.id")
    )
    title: Mapped[str] = mapped_column(String(255))
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(512))
    parser: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    error: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None]
    chunk_count: Mapped[int | None]
    sha256: Mapped[str | None] = mapped_column(String(64))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunkModel(BaseModel):
    __tablename__ = "document_chunks"
    __table_args__ = {"schema": "agent"}

    project_id: Mapped[UUID]
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent.document_collections.id")
    )
    document_id: Mapped[UUID] = mapped_column(ForeignKey("agent.documents.id"))
    content: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int]
    token_count: Mapped[int | None]
    page_number: Mapped[int | None]
    section_title: Mapped[str | None] = mapped_column(String(255))
    data: Mapped[dict | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))


class KnowledgeVersionModel(BaseModel):
    __tablename__ = "knowledge_versions"
    __table_args__ = (
        Index(
            "ix_knowledge_versions_agent_version", "agent_id", "version", unique=True
        ),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.agents.id"))
    version: Mapped[str] = mapped_column(String(32))
    collection_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PG_UUID), default=list)
    document_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PG_UUID))
    snapshot_metadata: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")


class SessionModel(BaseModel):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("project_id", "agent_id", "external_session_id"),
        CheckConstraint(
            "runtime_environment IN ('draft', 'staging', 'production')",
            name="ck_agent_sessions_runtime_environment",
        ),
        Index(
            "ix_agent_sessions_environment_activity",
            "project_id",
            "agent_id",
            "runtime_environment",
            "last_message_at",
            "id",
        ),
        Index(
            "ix_agent_sessions_chat_surface",
            "chat_surface_id",
            "status",
            "last_message_at",
        ),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.agents.id"))
    runtime_environment: Mapped[str] = mapped_column(
        String(16), default="draft", server_default=text("'draft'")
    )
    opened_release_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.agent_releases.id", ondelete="RESTRICT"), nullable=True
    )
    chat_surface_id: Mapped[UUID | None] = mapped_column(nullable=True)
    origin: Mapped[str] = mapped_column(
        String(32), default="runtime_api", server_default=text("'runtime_api'")
    )
    external_session_id: Mapped[str | None] = mapped_column(String(255))
    tenant_id: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active")
    mode: Mapped[str] = mapped_column(String(32), default="chat")
    data: Mapped[dict | None] = mapped_column(JSONB)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MessageModel(BaseModel):
    __tablename__ = "messages"
    __table_args__ = {"schema": "agent"}

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.agents.id"))
    session_id: Mapped[UUID] = mapped_column(ForeignKey("agent.sessions.id"))
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 8))
    data: Mapped[dict | None] = mapped_column(JSONB)


class AskJobModel(BaseModel):
    __tablename__ = "ask_jobs"
    __table_args__ = (
        Index("ix_ask_jobs_status_created", "status", "created_at"),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.agents.id"))
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent.sessions.id"))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    params: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[UUID | None] = mapped_column(PG_UUID)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentToolModel(BaseModel):
    __tablename__ = "tools"
    __table_args__ = (
        Index("ix_agent_tools_project_id", "project_id"),
        Index("ix_agent_tools_agent_id", "agent_id"),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.agents.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(64))
    config: Mapped[dict | None] = mapped_column(JSONB)
    input_schema: Mapped[dict | None] = mapped_column(JSONB)
    output_schema: Mapped[dict | None] = mapped_column(JSONB)
    risk_level: Mapped[str] = mapped_column(String(32), default="low")
    timeout_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="active")


class AgentToolSecretModel(BaseModel):
    __tablename__ = "tool_secrets"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        Index("ix_agent_tool_secrets_project_id", "project_id"),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(64))
    encrypted_value: Mapped[str] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)


class AgentOutboxEventModel(BaseModel):
    __tablename__ = "agent_outbox_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_agent_outbox_idempotency_key"),
        Index(
            "ix_agent_outbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('pending', 'retryable')"),
        ),
        Index("ix_agent_outbox_correlation_id", "correlation_id"),
        Index("ix_agent_outbox_aggregate", "aggregate_type", "aggregate_id"),
        {
            "schema": "agent",
            "comment": "Outbox events for the agent bounded context. Owned by module agent.",
        },
    )

    aggregate_type: Mapped[str] = mapped_column(String(128))
    aggregate_id: Mapped[UUID]
    event_type: Mapped[str] = mapped_column(String(255))
    event_version: Mapped[int] = mapped_column(Integer, default=1)
    routing_key: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255))
    correlation_id: Mapped[UUID]
    causation_id: Mapped[UUID | None]
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(128))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class AgentInboxEventModel(BaseModel):
    __tablename__ = "agent_inbox_events"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_agent_inbox_message_id"),
        UniqueConstraint("idempotency_key", name="uq_agent_inbox_idempotency_key"),
        Index(
            "ix_agent_inbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('received', 'retryable')"),
        ),
        Index("ix_agent_inbox_correlation_id", "correlation_id"),
        {
            "schema": "agent",
            "comment": "Inbox events for the agent bounded context. Owned by module agent.",
        },
    )

    message_id: Mapped[str] = mapped_column(String(255))
    producer_module: Mapped[str] = mapped_column(String(64))
    consumer_module: Mapped[str] = mapped_column(String(64), default="agent")
    event_type: Mapped[str] = mapped_column(String(255))
    event_version: Mapped[int] = mapped_column(Integer)
    routing_key: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    headers: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    correlation_id: Mapped[UUID]
    causation_id: Mapped[UUID | None]
    status: Mapped[str] = mapped_column(String(32), default="received")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(128))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
