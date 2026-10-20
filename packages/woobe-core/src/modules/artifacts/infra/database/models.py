from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, String, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import Base


class ArtifactRecord(Base):
    __abstract__ = True

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArtifactWorkspaceModel(ArtifactRecord):
    __tablename__ = 'workspaces'
    __table_args__ = (
        UniqueConstraint('project_id', 'environment', 'external_namespace', 'external_key', name='uq_artifact_workspace_external'),
        CheckConstraint("environment IN ('draft','staging','production')", name='ck_artifact_workspace_environment'),
        CheckConstraint("status IN ('active','archived','deletion_pending','purged')", name='ck_artifact_workspace_status'),
        CheckConstraint('version >= 1 AND catalog_version >= 0', name='ck_artifact_workspace_version'),
        CheckConstraint('quota_bytes >= 0 AND used_bytes >= 0 AND reserved_bytes >= 0 AND used_bytes + reserved_bytes <= quota_bytes', name='ck_artifact_workspace_quota'),
        CheckConstraint('retention_days >= 0', name='ck_artifact_workspace_retention'),
        ForeignKeyConstraint(['project_id', 'environment', 'default_profile_id', 'default_profile_revision'],
            ['artifacts.processing_profiles.project_id', 'artifacts.processing_profiles.environment', 'artifacts.processing_profiles.id', 'artifacts.processing_profiles.revision'], name='fk_artifact_workspace_profile'),
        CheckConstraint('(default_profile_id IS NULL) = (default_profile_revision IS NULL)', name='ck_artifact_workspace_profile_pair'),
        Index('ix_artifact_workspaces_scope_page', 'project_id', 'environment', 'id'),
        {'schema': 'artifacts'},
    )

    # Cross-context identity follows migration 0018: authority validates Project;
    # ORM metadata must not import Core internals to resolve a foreign table.
    project_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(16))
    external_namespace: Mapped[str] = mapped_column(String(255))
    external_key: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    storage_profile: Mapped[str] = mapped_column(String(128), default='local')
    status: Mapped[str] = mapped_column(String(32), default='active')
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    catalog_version: Mapped[int] = mapped_column(BigInteger, default=0)
    quota_bytes: Mapped[int] = mapped_column(BigInteger, default=1_073_741_824)
    used_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    labels: Mapped[dict] = mapped_column(JSONB, default=dict)
    creation_fingerprint: Mapped[str | None] = mapped_column(String(64))
    default_profile_id: Mapped[str | None] = mapped_column(String(128))
    default_profile_revision: Mapped[int | None] = mapped_column(BigInteger)


class ArtifactModel(ArtifactRecord):
    __tablename__ = 'artifacts'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id', name='uq_artifact_workspace_identity'),
        CheckConstraint("kind IN ('file','directory')", name='ck_artifact_kind'),
        CheckConstraint('version >= 1', name='ck_artifact_version'),
        CheckConstraint("kind <> 'directory' OR revision_id IS NULL", name='ck_artifact_directory_revision'),
        ForeignKeyConstraint(['id', 'revision_id'], ['artifacts.revisions.artifact_id', 'artifacts.revisions.id'],
                             name='fk_artifact_current_revision', use_alter=True, deferrable=True, initially='DEFERRED'),
        Index('uq_artifact_live_path', 'workspace_id', 'path', unique=True, postgresql_where=text('NOT deleted')),
        Index('ix_artifact_workspace_page', 'workspace_id', 'id'),
        {'schema': 'artifacts'},
    )

    workspace_id: Mapped[str] = mapped_column(ForeignKey('artifacts.workspaces.id', ondelete='RESTRICT'))
    path: Mapped[str] = mapped_column(String(1024))
    kind: Mapped[str] = mapped_column(String(16), default='file')
    revision_id: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class RevisionModel(ArtifactRecord):
    __tablename__ = 'revisions'
    __table_args__ = (
        UniqueConstraint('artifact_id', 'id', name='uq_artifact_revision_identity'),
        UniqueConstraint('object_key', name='uq_artifact_revision_object_key'),
        ForeignKeyConstraint(['workspace_id', 'artifact_id'], ['artifacts.artifacts.workspace_id', 'artifacts.artifacts.id'],
                             name='fk_artifact_revision_owner', ondelete='RESTRICT'),
        CheckConstraint('size_bytes >= 0', name='ck_artifact_revision_size'),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name='ck_artifact_revision_sha256'),
        CheckConstraint("origin IN ('upload','application','agent','tool','processing','copy')", name='ck_artifact_revision_origin'),
        Index('ix_artifact_revisions_page', 'workspace_id', 'artifact_id', 'id'),
        {'schema': 'artifacts'},
    )

    workspace_id: Mapped[str] = mapped_column(String(128))
    artifact_id: Mapped[str] = mapped_column(String(128))
    object_key: Mapped[str] = mapped_column(String(1024))
    content_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    origin: Mapped[str] = mapped_column(String(32))
    producer_id: Mapped[str | None] = mapped_column(String(128))
    storage_version_id: Mapped[str | None] = mapped_column(String(1024))
    operation_id: Mapped[str | None] = mapped_column(String(128))
    run_id: Mapped[str | None] = mapped_column(String(128))
    node_id: Mapped[str | None] = mapped_column(String(128))


class HeadHistoryModel(ArtifactRecord):
    __tablename__ = 'head_history'
    __table_args__ = (
        ForeignKeyConstraint(['workspace_id', 'artifact_id'], ['artifacts.artifacts.workspace_id', 'artifacts.artifacts.id'],
                             name='fk_artifact_history_owner', ondelete='RESTRICT'),
        ForeignKeyConstraint(['artifact_id', 'revision_id'], ['artifacts.revisions.artifact_id', 'artifacts.revisions.id'],
                             name='fk_artifact_history_revision'),
        UniqueConstraint('artifact_id', 'from_catalog_version', name='uq_artifact_history_version'),
        CheckConstraint('from_catalog_version > 0 AND (until_catalog_version IS NULL OR until_catalog_version > from_catalog_version)', name='ck_artifact_history_interval'),
        Index('uq_artifact_history_current', 'artifact_id', unique=True, postgresql_where=text('until_catalog_version IS NULL')),
        Index('ix_artifact_history_visibility', 'workspace_id', 'from_catalog_version', 'until_catalog_version', 'artifact_id'),
        {'schema': 'artifacts'},
    )

    workspace_id: Mapped[str] = mapped_column(String(128))
    artifact_id: Mapped[str] = mapped_column(String(128))
    from_catalog_version: Mapped[int] = mapped_column(BigInteger)
    until_catalog_version: Mapped[int | None] = mapped_column(BigInteger)
    path: Mapped[str] = mapped_column(String(1024))
    kind: Mapped[str] = mapped_column(String(16))
    revision_id: Mapped[str | None] = mapped_column(String(128))
    artifact_version: Mapped[int] = mapped_column(BigInteger)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class GrantModel(ArtifactRecord):
    __tablename__ = 'grants'
    __table_args__ = (
        CheckConstraint('(workspace_id IS NULL) <> (external_namespace IS NULL)', name='ck_artifact_grant_selector'),
        CheckConstraint('revision >= 1', name='ck_artifact_grant_revision'),
        Index('ix_artifact_grants_principal_scope', 'principal_id', 'project_id', 'environment'),
        {'schema': 'artifacts'},
    )

    project_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(16))
    principal_id: Mapped[str] = mapped_column(String(128))
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey('artifacts.workspaces.id', ondelete='RESTRICT'))
    external_namespace: Mapped[str | None] = mapped_column(String(255))
    actions: Mapped[list[str]] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(BigInteger, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class UploadModel(ArtifactRecord):
    __tablename__ = 'uploads'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'operation_id', name='uq_artifact_upload_operation'),
        CheckConstraint('expected_size >= 0 AND "offset" >= 0 AND "offset" <= expected_size', name='ck_artifact_upload_offset'),
        CheckConstraint("status IN ('created','uploading','verifying','committed','failed','aborted','expired')", name='ck_artifact_upload_status'),
        CheckConstraint("(status = 'committed') = (receipt IS NOT NULL)", name='ck_artifact_upload_receipt'),
        Index('ix_artifact_upload_expiration', 'status', 'expires_at'),
        {'schema': 'artifacts'},
    )

    workspace_id: Mapped[str] = mapped_column(ForeignKey('artifacts.workspaces.id', ondelete='RESTRICT'))
    operation_id: Mapped[str] = mapped_column(String(128))
    principal_id: Mapped[str] = mapped_column(String(128))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    expected_size: Mapped[int] = mapped_column(BigInteger)
    expected_sha256: Mapped[str] = mapped_column(String(64))
    content_type: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(1024))
    artifact_id: Mapped[str | None] = mapped_column(String(128))
    expected_revision: Mapped[str | None] = mapped_column(String(128))
    planned_revision_id: Mapped[str] = mapped_column(String(128))
    origin: Mapped[str] = mapped_column(String(32), default='upload')
    run_id: Mapped[str | None] = mapped_column(String(128))
    node_id: Mapped[str | None] = mapped_column(String(128))
    offset: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default='created')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    receipt: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    parts: Mapped[list[dict]] = mapped_column(JSONB, default=list)


# Keep repository-local imports stable without registering a second ORM class
# named WorkspaceModel alongside the Identity bounded context.
WorkspaceModel = ArtifactWorkspaceModel


class ArtifactEventModel(ArtifactRecord):
    __tablename__ = 'events'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'operation_id', 'kind', name='uq_artifact_event_operation'),
        Index('ix_artifact_events_delivery', 'delivered_at', 'created_at', 'id'),
        {'schema': 'artifacts'},
    )

    workspace_id: Mapped[str] = mapped_column(ForeignKey('artifacts.workspaces.id', ondelete='RESTRICT'))
    operation_id: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSONB)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CatalogOperationModel(ArtifactRecord):
    __tablename__ = 'catalog_operations'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'operation_id', name='uq_artifact_catalog_operation'),
        {'schema': 'artifacts'},
    )

    workspace_id: Mapped[str] = mapped_column(ForeignKey('artifacts.workspaces.id', ondelete='RESTRICT'))
    principal_id: Mapped[str] = mapped_column(String(128))
    operation_id: Mapped[str] = mapped_column(String(128))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    receipt: Mapped[dict] = mapped_column(JSONB)


class ProcessingProfileModel(Base):
    __tablename__ = 'processing_profiles'
    __table_args__ = (
        CheckConstraint("environment IN ('draft','staging','production')", name='ck_artifact_processing_profile_environment'),
        CheckConstraint('revision >= 1', name='ck_artifact_processing_profile_revision'),
        CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name='ck_artifact_processing_profile_fingerprint'),
        {'schema': 'artifacts'},
    )

    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    environment: Mapped[str] = mapped_column(String(16), primary_key=True)
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    revision: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    fingerprint: Mapped[str] = mapped_column(String(64))
    recipe: Mapped[dict] = mapped_column(JSONB)
