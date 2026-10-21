from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, String, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.outbox import OutboxEventModel as SharedOutboxEventModel
from shared.infra.database.inbox import InboxEventModel as SharedInboxEventModel
from shared.infra.database.base import Base


class ArtifactRecord(Base):
    __abstract__ = True

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArtifactWorkspaceModel(ArtifactRecord):
    __tablename__ = 'workspaces'
    __table_args__ = (
        UniqueConstraint('project_id', 'environment', 'external_namespace', 'external_key', name='uq_artifact_workspace_external'),
        UniqueConstraint('project_id', 'environment', 'id', name='uq_artifact_workspace_scope_identity'),
        CheckConstraint("environment IN ('draft','staging','production')", name='ck_artifact_workspace_environment'),
        CheckConstraint("status IN ('active','archived','deletion_pending','purged')", name='ck_artifact_workspace_status'),
        CheckConstraint('version >= 1 AND catalog_version >= 0', name='ck_artifact_workspace_version'),
        CheckConstraint('search_version >= 0', name='ck_artifact_workspace_search_version'),
        CheckConstraint('processing_sequence >= 0', name='ck_artifact_workspace_processing_sequence'),
        CheckConstraint('quota_bytes >= 0 AND used_bytes >= 0 AND reserved_bytes >= 0 AND used_bytes + reserved_bytes <= quota_bytes', name='ck_artifact_workspace_quota'),
        CheckConstraint('retention_days >= 0', name='ck_artifact_workspace_retention'),
        ForeignKeyConstraint(['project_id', 'environment', 'default_profile_id', 'default_profile_revision'],
            ['artifacts.processing_profiles.project_id', 'artifacts.processing_profiles.environment', 'artifacts.processing_profiles.id', 'artifacts.processing_profiles.revision'], name='fk_artifact_workspace_profile'),
        CheckConstraint('(default_profile_id IS NULL) = (default_profile_revision IS NULL)', name='ck_artifact_workspace_profile_pair'),
        Index('ix_artifact_workspaces_scope_page', 'project_id', 'environment', 'id'),
        Index('ix_artifact_workspace_retention', 'status', 'archived_at', 'id'),
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
    search_version: Mapped[int] = mapped_column(BigInteger, default=0)
    quota_bytes: Mapped[int] = mapped_column(BigInteger, default=1_073_741_824)
    used_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    labels: Mapped[dict] = mapped_column(JSONB, default=dict)
    creation_fingerprint: Mapped[str | None] = mapped_column(String(64))
    default_profile_id: Mapped[str | None] = mapped_column(String(128))
    default_profile_revision: Mapped[int | None] = mapped_column(BigInteger)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_sequence: Mapped[int] = mapped_column(BigInteger, default=0)


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
        UniqueConstraint('workspace_id', 'artifact_id', 'id', name='uq_artifact_revision_scoped_identity'),
        UniqueConstraint('object_key', name='uq_artifact_revision_object_key'),
        ForeignKeyConstraint(['workspace_id', 'artifact_id'], ['artifacts.artifacts.workspace_id', 'artifacts.artifacts.id'],
                             name='fk_artifact_revision_owner', ondelete='RESTRICT'),
        CheckConstraint('size_bytes >= 0', name='ck_artifact_revision_size'),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name='ck_artifact_revision_sha256'),
        CheckConstraint("origin IN ('upload','application','agent','tool','processing','copy')", name='ck_artifact_revision_origin'),
        CheckConstraint("content_state IN ('available','deletion_pending','purged')", name='ck_artifact_revision_content_state'),
        Index('ix_artifact_revisions_page', 'workspace_id', 'artifact_id', 'id'),
        Index('ix_artifact_revision_retention', 'workspace_id', 'content_state', 'created_at', 'id'),
        CheckConstraint('(source_representation_set_id IS NULL) = (source_representation_entry_id IS NULL)', name='ck_artifact_revisions_representation_pair'),
        ForeignKeyConstraint(['workspace_id', 'source_representation_set_id', 'source_representation_entry_id'],
            ['artifacts.representation_entries.workspace_id', 'artifacts.representation_entries.representation_set_id', 'artifacts.representation_entries.id'],
            name='fk_artifact_revisions_representation', use_alter=True),
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
    source_representation_set_id: Mapped[str | None] = mapped_column(String(128))
    source_representation_entry_id: Mapped[str | None] = mapped_column(String(128))
    external_operation_ref: Mapped[str | None] = mapped_column(String(512))
    source_refs: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    content_state: Mapped[str] = mapped_column(String(32), default='available', server_default='available')


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
        Index('ix_artifact_history_search_path', text("to_tsvector('simple'::regconfig, normalize(regexp_replace(path, '[^[:alnum:]]+', ' ', 'g'), NFKC))"),
              postgresql_using='gin'),
        Index('ix_artifact_history_search_path_literal', 'path', postgresql_using='gin',
              postgresql_ops={'path': 'gin_trgm_ops'}),
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
        CheckConstraint('(source_representation_set_id IS NULL) = (source_representation_entry_id IS NULL)', name='ck_artifact_uploads_representation_pair'),
        ForeignKeyConstraint(['workspace_id', 'source_representation_set_id', 'source_representation_entry_id'],
            ['artifacts.representation_entries.workspace_id', 'artifacts.representation_entries.representation_set_id', 'artifacts.representation_entries.id'],
            name='fk_artifact_uploads_representation', use_alter=True),
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
    source_representation_set_id: Mapped[str | None] = mapped_column(String(128))
    source_representation_entry_id: Mapped[str | None] = mapped_column(String(128))
    producer_id: Mapped[str | None] = mapped_column(String(128))
    external_operation_ref: Mapped[str | None] = mapped_column(String(512))
    source_refs: Mapped[list[dict]] = mapped_column(JSONB, default=list)
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


class ProcessingJobModel(ArtifactRecord):
    __tablename__ = 'processing_jobs'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'operation_id', name='uq_artifact_processing_operation'),
        UniqueConstraint('project_id', 'environment', 'workspace_id', 'id', name='uq_artifact_job_scoped_identity'),
        UniqueConstraint('workspace_id', 'artifact_id', 'revision_id', 'id', name='uq_artifact_job_source_identity'),
        ForeignKeyConstraint(['project_id', 'environment', 'workspace_id'],
            ['artifacts.workspaces.project_id', 'artifacts.workspaces.environment', 'artifacts.workspaces.id'], name='fk_artifact_job_scope'),
        CheckConstraint('(profile_id IS NULL) = (profile_revision IS NULL)', name='ck_artifact_job_profile_pair'),
        ForeignKeyConstraint(['workspace_id', 'artifact_id'], ['artifacts.artifacts.workspace_id', 'artifacts.artifacts.id'], name='fk_artifact_job_owner'),
        ForeignKeyConstraint(['artifact_id', 'revision_id'], ['artifacts.revisions.artifact_id', 'artifacts.revisions.id'], name='fk_artifact_job_source'),
        ForeignKeyConstraint(['project_id', 'environment', 'profile_id', 'profile_revision'],
            ['artifacts.processing_profiles.project_id', 'artifacts.processing_profiles.environment', 'artifacts.processing_profiles.id', 'artifacts.processing_profiles.revision'], name='fk_artifact_job_profile'),
        CheckConstraint("status IN ('queued','running','succeeded','failed','cancel_requested','cancelled','uncertain')", name='ck_artifact_job_status'),
        CheckConstraint('attempt >= 0 AND fencing_token >= 0 AND max_attempts >= 1', name='ck_artifact_job_attempt'),
        CheckConstraint('generation_number >= 0', name='ck_artifact_job_generation'),
        Index('ix_artifact_processing_expired_lease', 'status', 'lease_until', 'id'),
        Index('ix_artifact_processing_claim', 'status', 'available_at', 'created_at', 'id'),
        Index('ix_artifact_processing_project_budget', 'project_id', 'status', 'lease_until'),
        Index('ix_artifact_processing_workspace_budget', 'workspace_id', 'status', 'lease_until'),
        {'schema': 'artifacts'},
    )

    project_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(16))
    workspace_id: Mapped[str] = mapped_column(ForeignKey('artifacts.workspaces.id', ondelete='RESTRICT'))
    artifact_id: Mapped[str] = mapped_column(String(128))
    revision_id: Mapped[str] = mapped_column(String(128))
    principal_id: Mapped[str] = mapped_column(String(128))
    principal_snapshot: Mapped[dict] = mapped_column(JSONB)
    operation_id: Mapped[str] = mapped_column(String(128))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    processing_fingerprint: Mapped[str] = mapped_column(String(64))
    profile_id: Mapped[str | None] = mapped_column(String(128))
    profile_revision: Mapped[int | None] = mapped_column(BigInteger)
    recipe: Mapped[dict] = mapped_column(JSONB)
    recipe_fingerprint: Mapped[str] = mapped_column(String(64))
    model_binding: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    generation_number: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(32), default='queued')
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    fencing_token: Mapped[int] = mapped_column(BigInteger, default=0)
    worker_id: Mapped[str | None] = mapped_column(String(128))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkpoints: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    error_code: Mapped[str | None] = mapped_column(String(128))
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)


class ProcessingAttemptModel(ArtifactRecord):
    __tablename__ = 'processing_attempts'
    __table_args__ = (
        UniqueConstraint('job_id', 'fencing_token', name='uq_artifact_processing_attempt_fence'),
        {'schema': 'artifacts'},
    )

    job_id: Mapped[str] = mapped_column(ForeignKey('artifacts.processing_jobs.id', ondelete='RESTRICT'))
    fencing_token: Mapped[int] = mapped_column(BigInteger)
    worker_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default='running')
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(128))


class ArtifactProcessingOutboxModel(SharedOutboxEventModel):
    __tablename__ = 'processing_outbox'
    __table_args__ = (
        UniqueConstraint('idempotency_key', name='uq_artifact_processing_outbox_idempotency'),
        Index('ix_artifact_processing_outbox_pending', 'status', 'available_at', 'created_at'),
        {'schema': 'artifacts'},
    )


class ArtifactProcessingInboxModel(SharedInboxEventModel):
    __tablename__ = 'processing_inbox'
    __table_args__ = (
        Index('ix_artifact_processing_inbox_job', text("(payload ->> 'job_id')")),
        UniqueConstraint('message_id', 'consumer_module', name='uq_artifact_processing_inbox_message'),
        UniqueConstraint('idempotency_key', name='uq_artifact_processing_inbox_idempotency'),
        {'schema': 'artifacts'},
    )


class ProcessingProjectQueueModel(Base):
    __tablename__ = 'processing_project_queue'
    __table_args__ = {'schema': 'artifacts'}

    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    last_claim_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProcessingWorkspaceQueueModel(Base):
    __tablename__ = 'processing_workspace_queue'
    __table_args__ = {'schema': 'artifacts'}

    workspace_id: Mapped[str] = mapped_column(String(128), ForeignKey('artifacts.workspaces.id', ondelete='RESTRICT'), primary_key=True)
    last_claim_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


from modules.artifacts.infra.database.representation_models import (  # noqa: E402
    ArtifactRepresentationEntryModel as ArtifactRepresentationEntryModel,
    ArtifactRepresentationHeadModel as ArtifactRepresentationHeadModel,
    ArtifactRepresentationSetModel as ArtifactRepresentationSetModel,
    ArtifactSourceBlockModel as ArtifactSourceBlockModel,
    ArtifactSourceSegmentModel as ArtifactSourceSegmentModel,
    ArtifactStoredObjectModel as ArtifactStoredObjectModel,
)

from modules.artifacts.infra.database.index_models import (  # noqa: E402
    ArtifactDocumentIndexModel as ArtifactDocumentIndexModel,
    ArtifactDocumentNodeModel as ArtifactDocumentNodeModel,
)

from modules.artifacts.infra.database.model_operation_models import ArtifactDocumentModelCallModel as ArtifactDocumentModelCallModel  # noqa: E402

from modules.artifacts.infra.database.run_source_models import (  # noqa: E402
    ArtifactRunSourceManifestModel as ArtifactRunSourceManifestModel,
    ArtifactRunSourceModel as ArtifactRunSourceModel,
)
