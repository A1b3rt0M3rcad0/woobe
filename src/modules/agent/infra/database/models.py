from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
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
    meta: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)


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
        Index("ix_agent_model_configs_agent_version", "agent_id", "version", unique=True),
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
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.agents.id"))
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="draft")
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
    system_prompt: Mapped[str | None] = mapped_column(Text)
    response_format: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
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
    session_mode: Mapped[str | None] = mapped_column(String(32))
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
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    position: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None]
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)


class AgentOutboxEventModel(BaseModel):
    __tablename__ = "outbox_events"
    __table_args__ = {"schema": "agent"}

    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    routing_key: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    correlation_id: Mapped[UUID | None]
    causation_id: Mapped[UUID | None]
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[UUID]


class AgentInboxEventModel(BaseModel):
    __tablename__ = "inbox_events"
    __table_args__ = (
        UniqueConstraint("message_id"),
        {"schema": "agent"},
    )

    message_id: Mapped[UUID]
    producer_module: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(255))
    event_version: Mapped[int] = mapped_column(Integer, default=1)
    routing_key: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
