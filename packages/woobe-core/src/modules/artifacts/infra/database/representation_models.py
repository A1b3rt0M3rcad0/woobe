from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Computed, DateTime, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import Base


class ArtifactRepresentationRecord(Base):
    __abstract__ = True
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArtifactStoredObjectModel(ArtifactRepresentationRecord):
    __tablename__ = 'stored_objects'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id', name='uq_artifact_stored_object_scope'),
        UniqueConstraint('workspace_id', 'object_key', name='uq_artifact_stored_object_key'),
        ForeignKeyConstraint(['project_id', 'environment', 'workspace_id', 'job_id'],
            ['artifacts.processing_jobs.project_id', 'artifacts.processing_jobs.environment',
             'artifacts.processing_jobs.workspace_id', 'artifacts.processing_jobs.id'], name='fk_artifact_stored_object_job'),
        CheckConstraint('size_bytes >= 0 AND fencing_token >= 1', name='ck_artifact_stored_object_bounds'),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name='ck_artifact_stored_object_digest'),
        CheckConstraint("state IN ('reserved','stored','referenced','gc_pending','purged')", name='ck_artifact_stored_object_state'),
        CheckConstraint("accounting_bucket IN ('reserved','used','none')", name='ck_artifact_stored_object_accounting'),
        CheckConstraint("(state = 'reserved' AND accounting_bucket = 'reserved') OR (state IN ('stored','referenced') AND accounting_bucket = 'used') OR (state = 'gc_pending' AND accounting_bucket IN ('reserved','used')) OR (state = 'purged' AND accounting_bucket = 'none')", name='ck_artifact_stored_object_state_accounting'),
        Index('ix_artifact_stored_object_gc', 'workspace_id', 'state', 'created_at'),
        {'schema': 'artifacts'},
    )
    project_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(16))
    workspace_id: Mapped[str] = mapped_column(String(128))
    job_id: Mapped[str] = mapped_column(String(128))
    fencing_token: Mapped[int] = mapped_column(BigInteger)
    object_key: Mapped[str] = mapped_column(String(1024))
    role: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    content_type: Mapped[str] = mapped_column(String(255))
    storage_version_id: Mapped[str | None] = mapped_column(String(1024))
    state: Mapped[str] = mapped_column(String(32), default='reserved')
    accounting_bucket: Mapped[str] = mapped_column(String(16), default='reserved')


class ArtifactRepresentationSetModel(ArtifactRepresentationRecord):
    __tablename__ = 'representation_sets'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'id', name='uq_artifact_representation_set_scope'),
        UniqueConstraint('workspace_id', 'artifact_id', 'revision_id', 'id', name='uq_artifact_representation_source_identity'),
        UniqueConstraint('job_id', name='uq_artifact_representation_job'),
        ForeignKeyConstraint(['workspace_id', 'artifact_id', 'revision_id', 'job_id'],
            ['artifacts.processing_jobs.workspace_id', 'artifacts.processing_jobs.artifact_id',
             'artifacts.processing_jobs.revision_id', 'artifacts.processing_jobs.id'], name='fk_artifact_representation_source_job'),
        ForeignKeyConstraint(['project_id', 'environment', 'workspace_id'],
            ['artifacts.workspaces.project_id', 'artifacts.workspaces.environment', 'artifacts.workspaces.id'], name='fk_artifact_representation_scope'),
        ForeignKeyConstraint(['workspace_id', 'manifest_object_id'],
            ['artifacts.stored_objects.workspace_id', 'artifacts.stored_objects.id'], name='fk_artifact_representation_manifest'),
        CheckConstraint("status IN ('building','ready','deletion_pending','purged')", name='ck_artifact_representation_status'),
        CheckConstraint('generation_number >= 0 AND build_fencing_token >= 1 AND publication_fencing_token >= 0', name='ck_artifact_representation_bounds'),
        CheckConstraint('entry_count >= 0 AND block_count >= 0 AND segment_count >= 0 AND page_count >= 0', name='ck_artifact_representation_counts'),
        CheckConstraint("status <> 'ready' OR published_search_version IS NOT NULL", name='ck_artifact_representation_search_version'),
        CheckConstraint("coverage IN ('complete','partial','needs_ocr','unsupported')", name='ck_artifact_representation_coverage'),
        CheckConstraint("source_sha256 ~ '^[0-9a-f]{64}$' AND recipe_fingerprint ~ '^[0-9a-f]{64}$' AND processing_fingerprint ~ '^[0-9a-f]{64}$'", name='ck_artifact_representation_digests'),
        CheckConstraint('(profile_id IS NULL) = (profile_revision IS NULL)', name='ck_artifact_representation_profile_pair'),
        ForeignKeyConstraint(['project_id', 'environment', 'profile_id', 'profile_revision'],
            ['artifacts.processing_profiles.project_id', 'artifacts.processing_profiles.environment',
             'artifacts.processing_profiles.id', 'artifacts.processing_profiles.revision'], name='fk_artifact_representation_profile'),
        Index('ix_artifact_representation_reuse', 'workspace_id', 'artifact_id', 'revision_id', 'processing_fingerprint', 'status'),
        Index('ix_artifact_representation_page', 'workspace_id', 'artifact_id', 'revision_id', 'generation_number', 'id'),
        {'schema': 'artifacts'},
    )
    project_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(16))
    workspace_id: Mapped[str] = mapped_column(String(128))
    artifact_id: Mapped[str] = mapped_column(String(128))
    revision_id: Mapped[str] = mapped_column(String(128))
    job_id: Mapped[str] = mapped_column(String(128))
    generation_number: Mapped[int] = mapped_column(BigInteger)
    build_fencing_token: Mapped[int] = mapped_column(BigInteger)
    publication_fencing_token: Mapped[int] = mapped_column(BigInteger, default=0)
    published_search_version: Mapped[int | None] = mapped_column(BigInteger)
    source_sha256: Mapped[str] = mapped_column(String(64))
    recipe_fingerprint: Mapped[str] = mapped_column(String(64))
    processing_fingerprint: Mapped[str] = mapped_column(String(64))
    profile_id: Mapped[str | None] = mapped_column(String(128))
    profile_revision: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32), default='building')
    coverage: Mapped[str] = mapped_column(String(32), default='unsupported')
    manifest_object_id: Mapped[str | None] = mapped_column(String(128))
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    metadata_fingerprint: Mapped[str | None] = mapped_column(String(64))
    sealed: Mapped[bool] = mapped_column(Boolean, default=False)
    entry_count: Mapped[int] = mapped_column(Integer, default=0)
    block_count: Mapped[int] = mapped_column(Integer, default=0)
    segment_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    diagnostics: Mapped[list] = mapped_column(JSONB, default=list)
    pages: Mapped[list] = mapped_column(JSONB, default=list)


class ArtifactRepresentationEntryModel(ArtifactRepresentationRecord):
    __tablename__ = 'representation_entries'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'representation_set_id', 'id', name='uq_artifact_representation_entry_scope'),
        UniqueConstraint('representation_set_id', 'path', name='uq_artifact_representation_path'),
        UniqueConstraint('representation_set_id', 'asset_id', name='uq_artifact_representation_asset'),
        ForeignKeyConstraint(['workspace_id', 'representation_set_id'],
            ['artifacts.representation_sets.workspace_id', 'artifacts.representation_sets.id'], name='fk_artifact_representation_entry_set'),
        ForeignKeyConstraint(['workspace_id', 'object_id'],
            ['artifacts.stored_objects.workspace_id', 'artifacts.stored_objects.id'], name='fk_artifact_representation_entry_object'),
        Index('ix_artifact_representation_entry_page', 'representation_set_id', 'path', 'id'),
        {'schema': 'artifacts'},
    )
    workspace_id: Mapped[str] = mapped_column(String(128))
    representation_set_id: Mapped[str] = mapped_column(String(128))
    object_id: Mapped[str] = mapped_column(String(128))
    path: Mapped[str] = mapped_column(String(1024))
    role: Mapped[str] = mapped_column(String(32))
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    asset_id: Mapped[str | None] = mapped_column(String(128))


class ArtifactSourceBlockModel(ArtifactRepresentationRecord):
    __tablename__ = 'source_blocks'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'representation_set_id', 'block_id', name='uq_artifact_source_block_scope'),
        UniqueConstraint('representation_set_id', 'ordinal', name='uq_artifact_source_block_ordinal'),
        ForeignKeyConstraint(['workspace_id', 'representation_set_id'],
            ['artifacts.representation_sets.workspace_id', 'artifacts.representation_sets.id'], name='fk_artifact_source_block_set'),
        ForeignKeyConstraint(['workspace_id', 'object_id'],
            ['artifacts.stored_objects.workspace_id', 'artifacts.stored_objects.id'], name='fk_artifact_source_block_object'),
        ForeignKeyConstraint(['workspace_id', 'representation_set_id', 'parent_block_id'],
            ['artifacts.source_blocks.workspace_id', 'artifacts.source_blocks.representation_set_id', 'artifacts.source_blocks.block_id'],
            name='fk_artifact_source_block_parent', deferrable=True, initially='DEFERRED'),
        CheckConstraint('ordinal >= 0 AND char_length >= 0 AND byte_start >= 0 AND byte_end >= byte_start', name='ck_artifact_source_block_bounds'),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name='ck_artifact_source_block_digest'),
        Index('ix_artifact_source_block_page', 'representation_set_id', 'ordinal'),
        {'schema': 'artifacts'},
    )
    workspace_id: Mapped[str] = mapped_column(String(128))
    representation_set_id: Mapped[str] = mapped_column(String(128))
    block_id: Mapped[str] = mapped_column(String(128))
    ordinal: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    parent_block_id: Mapped[str | None] = mapped_column(String(128))
    source_locator: Mapped[dict] = mapped_column(JSONB)
    extraction_method: Mapped[str] = mapped_column(String(16))
    inferred: Mapped[bool] = mapped_column(Boolean, default=False)
    asset_ids: Mapped[list] = mapped_column(JSONB, default=list)
    object_id: Mapped[str | None] = mapped_column(String(128))
    byte_start: Mapped[int] = mapped_column(BigInteger)
    byte_end: Mapped[int] = mapped_column(BigInteger)
    char_length: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))


class ArtifactSourceSegmentModel(ArtifactRepresentationRecord):
    __tablename__ = 'source_segments'
    __table_args__ = (
        UniqueConstraint('representation_set_id', 'block_id', 'char_start', name='uq_artifact_source_segment_start'),
        ForeignKeyConstraint(['workspace_id', 'representation_set_id', 'block_id'],
            ['artifacts.source_blocks.workspace_id', 'artifacts.source_blocks.representation_set_id', 'artifacts.source_blocks.block_id'], name='fk_artifact_source_segment_block'),
        CheckConstraint('char_start >= 0 AND char_end > char_start AND byte_start >= 0 AND byte_end > byte_start', name='ck_artifact_source_segment_bounds'),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name='ck_artifact_source_segment_digest'),
        Index('ix_artifact_source_segment_search_vector', 'search_vector', postgresql_using='gin'),
        Index('ix_artifact_source_segment_search_literal', 'search_normalized', postgresql_using='gin',
              postgresql_ops={'search_normalized': 'gin_trgm_ops'}),
        {'schema': 'artifacts'},
    )
    workspace_id: Mapped[str] = mapped_column(String(128))
    representation_set_id: Mapped[str] = mapped_column(String(128))
    block_id: Mapped[str] = mapped_column(String(128))
    char_start: Mapped[int] = mapped_column(BigInteger)
    char_end: Mapped[int] = mapped_column(BigInteger)
    byte_start: Mapped[int] = mapped_column(BigInteger)
    byte_end: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    search_text: Mapped[str] = mapped_column(Text, server_default=text("''"))
    search_normalized: Mapped[str] = mapped_column(Text, server_default=text("''"))
    search_vector: Mapped[object] = mapped_column(TSVECTOR,
        Computed("to_tsvector('simple'::regconfig, search_normalized)", persisted=True))


class ArtifactRepresentationHeadModel(Base):
    __tablename__ = 'representation_heads'
    __table_args__ = (
        ForeignKeyConstraint(['workspace_id', 'artifact_id', 'revision_id'],
            ['artifacts.revisions.workspace_id', 'artifacts.revisions.artifact_id', 'artifacts.revisions.id'], name='fk_artifact_representation_head_source'),
        ForeignKeyConstraint(['workspace_id', 'artifact_id', 'revision_id', 'representation_set_id'],
            ['artifacts.representation_sets.workspace_id', 'artifacts.representation_sets.artifact_id',
             'artifacts.representation_sets.revision_id', 'artifacts.representation_sets.id'], name='fk_artifact_representation_head_set'),
        CheckConstraint('request_number >= 0', name='ck_artifact_representation_head_number'),
        {'schema': 'artifacts'},
    )
    workspace_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(String(128))
    revision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    representation_set_id: Mapped[str] = mapped_column(String(128))
    request_number: Mapped[int] = mapped_column(BigInteger)
