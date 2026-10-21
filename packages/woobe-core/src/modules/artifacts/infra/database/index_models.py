from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import Base


class ArtifactDocumentIndexModel(Base):
    __tablename__ = 'document_indexes'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'representation_set_id', 'id', name='uq_artifact_document_index_generation'),
        UniqueConstraint('job_id', name='uq_artifact_document_index_job'),
        ForeignKeyConstraint(['workspace_id', 'artifact_id', 'revision_id', 'representation_set_id'],
            ['artifacts.representation_sets.workspace_id', 'artifacts.representation_sets.artifact_id',
             'artifacts.representation_sets.revision_id', 'artifacts.representation_sets.id'], name='fk_artifact_document_index_generation'),
        ForeignKeyConstraint(['workspace_id', 'artifact_id', 'revision_id', 'job_id'],
            ['artifacts.processing_jobs.workspace_id', 'artifacts.processing_jobs.artifact_id',
             'artifacts.processing_jobs.revision_id', 'artifacts.processing_jobs.id'], name='fk_artifact_document_index_source_job'),
        ForeignKeyConstraint(['workspace_id', 'id', 'root_node_id'],
            ['artifacts.document_nodes.workspace_id', 'artifacts.document_nodes.document_index_id', 'artifacts.document_nodes.id'],
            name='fk_artifact_document_index_root_node', deferrable=True, initially='DEFERRED', use_alter=True),
        ForeignKeyConstraint(['project_id', 'environment', 'workspace_id', 'job_id'],
            ['artifacts.processing_jobs.project_id', 'artifacts.processing_jobs.environment',
             'artifacts.processing_jobs.workspace_id', 'artifacts.processing_jobs.id'], name='fk_artifact_document_index_job'),
        ForeignKeyConstraint(['workspace_id', 'manifest_object_id'],
            ['artifacts.stored_objects.workspace_id', 'artifacts.stored_objects.id'], name='fk_artifact_document_index_manifest'),
        CheckConstraint("status IN ('building','ready','deletion_pending','purged')", name='ck_artifact_document_index_status'),
        CheckConstraint("tree_kind IN ('headings','canonical','pages','blocks','empty')", name='ck_artifact_document_index_kind'),
        CheckConstraint("coverage IN ('complete','partial','needs_ocr','unsupported')", name='ck_artifact_document_index_coverage'),
        CheckConstraint('build_fencing_token >= 1 AND publication_fencing_token >= 0 AND node_count >= 0 AND node_count <= 110001 AND source_block_count >= 0 AND source_block_count <= 100000 AND max_depth >= 0 AND max_depth <= 64', name='ck_artifact_document_index_bounds'),
        CheckConstraint("source_sha256 ~ '^[0-9a-f]{64}$' AND recipe_fingerprint ~ '^[0-9a-f]{64}$' AND processing_fingerprint ~ '^[0-9a-f]{64}$'", name='ck_artifact_document_index_digests'),
        Index('ix_artifact_document_index_reuse', 'workspace_id', 'representation_set_id', 'processing_fingerprint', 'status'),
        {'schema': 'artifacts'},
    )
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    project_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(16))
    workspace_id: Mapped[str] = mapped_column(String(128))
    artifact_id: Mapped[str] = mapped_column(String(128))
    revision_id: Mapped[str] = mapped_column(String(128))
    representation_set_id: Mapped[str] = mapped_column(String(128))
    job_id: Mapped[str] = mapped_column(String(128))
    source_sha256: Mapped[str] = mapped_column(String(64))
    recipe_fingerprint: Mapped[str] = mapped_column(String(64))
    processing_fingerprint: Mapped[str] = mapped_column(String(64))
    engine: Mapped[str] = mapped_column(String(128))
    engine_version: Mapped[str] = mapped_column(String(64))
    build_fencing_token: Mapped[int] = mapped_column(BigInteger)
    publication_fencing_token: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(32), default='building')
    sealed: Mapped[bool] = mapped_column(Boolean, default=False)
    tree_kind: Mapped[str] = mapped_column(String(16), default='empty')
    coverage: Mapped[str] = mapped_column(String(16), default='unsupported')
    root_node_id: Mapped[str | None] = mapped_column(String(128))
    node_count: Mapped[int] = mapped_column(Integer, default=0)
    source_block_count: Mapped[int] = mapped_column(Integer, default=0)
    max_depth: Mapped[int] = mapped_column(Integer, default=0)
    manifest_object_id: Mapped[str | None] = mapped_column(String(128))
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    metadata_fingerprint: Mapped[str | None] = mapped_column(String(64))


class ArtifactDocumentNodeModel(Base):
    __tablename__ = 'document_nodes'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'document_index_id', 'id', name='uq_artifact_document_node_scope'),
        UniqueConstraint('document_index_id', 'ordinal', name='uq_artifact_document_node_ordinal'),
        UniqueConstraint('document_index_id', 'block_id', name='uq_artifact_document_node_block'),
        ForeignKeyConstraint(['workspace_id', 'representation_set_id', 'document_index_id'],
            ['artifacts.document_indexes.workspace_id', 'artifacts.document_indexes.representation_set_id',
             'artifacts.document_indexes.id'], name='fk_artifact_document_node_index'),
        ForeignKeyConstraint(['workspace_id', 'document_index_id', 'parent_id'],
            ['artifacts.document_nodes.workspace_id', 'artifacts.document_nodes.document_index_id', 'artifacts.document_nodes.id'],
            name='fk_artifact_document_node_parent', deferrable=True, initially='DEFERRED'),
        ForeignKeyConstraint(['workspace_id', 'representation_set_id', 'block_id'],
            ['artifacts.source_blocks.workspace_id', 'artifacts.source_blocks.representation_set_id',
             'artifacts.source_blocks.block_id'], name='fk_artifact_document_node_source'),
        CheckConstraint('ordinal >= 0 AND depth >= 0 AND depth <= 64 AND children_count >= 0 AND (page_index IS NULL OR page_index >= 0)', name='ck_artifact_document_node_bounds'),
        CheckConstraint("kind IN ('root','section','page','block')", name='ck_artifact_document_node_kind'),
        CheckConstraint('(block_id IS NULL) = (block_sha256 IS NULL)', name='ck_artifact_document_node_source_pair'),
        CheckConstraint("block_sha256 IS NULL OR block_sha256 ~ '^[0-9a-f]{64}$'", name='ck_artifact_document_node_digest'),
        Index('ix_artifact_document_node_children', 'document_index_id', 'parent_id', 'ordinal'),
        {'schema': 'artifacts'},
    )
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    workspace_id: Mapped[str] = mapped_column(String(128))
    representation_set_id: Mapped[str] = mapped_column(String(128))
    document_index_id: Mapped[str] = mapped_column(String(128))
    parent_id: Mapped[str | None] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(16))
    ordinal: Mapped[int] = mapped_column(Integer)
    depth: Mapped[int] = mapped_column(Integer)
    children_count: Mapped[int] = mapped_column(Integer)
    source_ranges: Mapped[list] = mapped_column(JSONB)
    block_id: Mapped[str | None] = mapped_column(String(128))
    block_sha256: Mapped[str | None] = mapped_column(String(64))
    page_index: Mapped[int | None] = mapped_column(Integer)
