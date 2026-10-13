"""Central configuration persistence. No consumer module owns these values."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, ForeignKeyConstraint,
                        Index, String, Text, UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import Base, BaseModel


class ConfigurationLegacyAuthorityModel(Base):
    __tablename__ = "project_configuration_legacy_authorities"
    __table_args__ = {"schema": "core"}
    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id", ondelete="CASCADE"), primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    subject_id: Mapped[UUID] = mapped_column(primary_key=True)
    permission: Mapped[str] = mapped_column(String(64), primary_key=True)
    catalog_revision: Mapped[str] = mapped_column(String(64))


class ConfigurationReferenceModel(BaseModel):
    __tablename__ = "project_configuration_references"
    __table_args__ = (
        ForeignKeyConstraint(["key_id", "project_id"],
                             ["core.project_environment_keys.id", "core.project_environment_keys.project_id"],
                             ondelete="RESTRICT"),
        UniqueConstraint("project_id", "consumer_kind", "consumer_id", "definition_revision", "field_path", "key_id"),
        Index("ix_configuration_reference_key", "project_id", "key_id"),
        {"schema": "core"},
    )
    project_id: Mapped[UUID]
    key_id: Mapped[UUID]
    consumer_kind: Mapped[str] = mapped_column(String(32))
    consumer_id: Mapped[UUID]
    definition_revision: Mapped[str] = mapped_column(String(128))
    field_path: Mapped[str] = mapped_column(String(512))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    retained: Mapped[bool] = mapped_column(Boolean, default=True)
    destination: Mapped[str] = mapped_column(Text, default="")


class ConfigurationUsePolicyModel(BaseModel):
    __tablename__ = "project_configuration_use_policies"
    __table_args__ = (
        ForeignKeyConstraint(["key_id", "project_id"],
                             ["core.project_environment_keys.id", "core.project_environment_keys.project_id"],
                             ondelete="RESTRICT"),
        UniqueConstraint("project_id", "key_id", "consumer_kind", "consumer_scope", "destination_id"),
        Index("ix_configuration_policy_consumer", "project_id", "consumer_kind", "consumer_scope"),
        {"schema": "core"},
    )
    project_id: Mapped[UUID]
    key_id: Mapped[UUID]
    consumer_kind: Mapped[str] = mapped_column(String(32))
    consumer_scope: Mapped[str] = mapped_column(String(36))
    destination: Mapped[str] = mapped_column(Text)
    destination_id: Mapped[str] = mapped_column(String(64))
    environments: Mapped[list[str]] = mapped_column(JSONB)
    field_paths: Mapped[list[str]] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    actor: Mapped[str] = mapped_column(String(128))


class ConfigurationValueVersionModel(BaseModel):
    __tablename__ = "project_configuration_value_versions"
    __table_args__ = (
        ForeignKeyConstraint(["key_id", "project_id"],
                             ["core.project_environment_keys.id", "core.project_environment_keys.project_id"],
                             ondelete="RESTRICT"),
        UniqueConstraint("key_id", "value_version"),
        Index("ix_configuration_version_retention", "expires_at"),
        {"schema": "core"},
    )
    project_id: Mapped[UUID]
    key_id: Mapped[UUID]
    value_version: Mapped[UUID]
    source: Mapped[str] = mapped_column(String(64))
    stored_value: Mapped[str] = mapped_column(Text)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LegacyConfigurationAliasModel(BaseModel):
    __tablename__ = "project_configuration_legacy_aliases"
    __table_args__ = (
        ForeignKeyConstraint(["key_id", "project_id"],
                             ["core.project_environment_keys.id", "core.project_environment_keys.project_id"],
                             ondelete="RESTRICT"),
        UniqueConstraint("project_id", "source_kind", "source_id", "field_path"),
        Index("ix_configuration_legacy_project", "project_id", "state"),
        {"schema": "core"},
    )
    project_id: Mapped[UUID]
    key_id: Mapped[UUID]
    source_kind: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[UUID]
    field_path: Mapped[str] = mapped_column(String(512))
    source_revision: Mapped[str] = mapped_column(String(128))
    routes: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    state: Mapped[str] = mapped_column(String(24), default="eligible")
    revision: Mapped[int] = mapped_column(BigInteger, default=1)


class LegacyConfigurationValueModel(BaseModel):
    __tablename__ = "project_configuration_legacy_values"
    __table_args__ = (UniqueConstraint("alias_id"), {"schema": "core"})
    alias_id: Mapped[UUID] = mapped_column(ForeignKey("core.project_configuration_legacy_aliases.id", ondelete="CASCADE"))
    stored_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_version: Mapped[UUID]
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    material_state: Mapped[str] = mapped_column(String(24), default="present")
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class ConfigurationLeaseModel(BaseModel):
    __tablename__ = "project_configuration_leases"
    __table_args__ = (
        UniqueConstraint("project_id", "run_id"),
        Index("ix_configuration_lease_expiry", "expires_at"),
        {"schema": "core"},
    )
    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id", ondelete="CASCADE"))
    run_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(16))
    pins: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    dependency_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConfigurationValidationModel(BaseModel):
    __tablename__ = "project_configuration_validations"
    __table_args__ = (
        Index("ix_configuration_validation_consumer", "project_id", "consumer_kind", "consumer_id", "environment"),
        {"schema": "core"},
    )
    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id", ondelete="CASCADE"))
    consumer_kind: Mapped[str] = mapped_column(String(32))
    consumer_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(24))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)
    actor: Mapped[str] = mapped_column(String(128))


class ConfigurationAuditModel(BaseModel):
    __tablename__ = "project_configuration_audit"
    __table_args__ = (Index("ix_configuration_audit_project", "project_id", "created_at"), {"schema": "core"})
    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id", ondelete="CASCADE"))
    operation: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(128))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class ConfigurationMutationModel(BaseModel):
    __tablename__ = "project_configuration_mutations"
    __table_args__ = (UniqueConstraint("project_id", "actor", "request_id"), {"schema": "core"})
    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id", ondelete="CASCADE"))
    actor: Mapped[str] = mapped_column(String(128))
    request_id: Mapped[str] = mapped_column(String(128))
    request_mac: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)


class ConfigurationMigrationModel(BaseModel):
    __tablename__ = "project_configuration_migrations"
    __table_args__ = (Index("ix_configuration_migration_project", "project_id", "state"), {"schema": "core"})
    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id", ondelete="CASCADE"))
    state: Mapped[str] = mapped_column(String(24), default="discovered")
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB)
    progress: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    actor: Mapped[str] = mapped_column(String(128))


class ConfigurationHistoricalEvidenceModel(BaseModel):
    __tablename__ = "project_configuration_historical_evidence"
    __table_args__ = (UniqueConstraint("project_id", "resource_kind", "resource_id", "definition_revision"), {"schema": "core"})
    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id", ondelete="CASCADE"))
    resource_kind: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[UUID]
    definition_revision: Mapped[str] = mapped_column(String(128))
    original_ciphertext: Mapped[str] = mapped_column(Text)
    original_sha256: Mapped[str] = mapped_column(String(64))
    projection: Mapped[dict[str, Any]] = mapped_column(JSONB)
    interpretation: Mapped[dict[str, Any]] = mapped_column(JSONB)


class ConfigurationProcessModel(BaseModel):
    __tablename__ = "project_configuration_processes"
    __table_args__ = (UniqueConstraint("process_identity"), {"schema": "core"})
    process_identity: Mapped[str] = mapped_column(String(255))
    capabilities: Mapped[list[str]] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LegacyConfigurationConsumerModel(Base):
    """Closed consumer set captured by an owner migration, never a public grant."""
    __tablename__ = "project_configuration_legacy_consumers"
    __table_args__ = {"schema": "core"}
    alias_id: Mapped[UUID] = mapped_column(ForeignKey("core.project_configuration_legacy_aliases.id", ondelete="CASCADE"), primary_key=True)
    consumer_kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    consumer_id: Mapped[UUID] = mapped_column(primary_key=True)
    field_path: Mapped[str] = mapped_column(String(512), primary_key=True)
