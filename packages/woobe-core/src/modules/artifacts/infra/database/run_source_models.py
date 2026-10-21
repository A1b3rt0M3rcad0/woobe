from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKeyConstraint, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import Base


class ArtifactRunSourceManifestModel(Base):
    __tablename__ = 'run_source_manifests'
    __table_args__ = (
        UniqueConstraint('project_id', 'environment', 'workspace_id', 'run_id', name='uq_artifact_run_source_manifest'),
        ForeignKeyConstraint(['project_id', 'environment', 'workspace_id'],
            ['artifacts.workspaces.project_id', 'artifacts.workspaces.environment', 'artifacts.workspaces.id'],
            name='fk_artifact_run_source_manifest_workspace', ondelete='RESTRICT'),
        CheckConstraint("environment IN ('draft','staging','production')", name='ck_artifact_run_source_manifest_environment'),
        CheckConstraint("run_id ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$'", name='ck_artifact_run_source_manifest_run_id'),
        CheckConstraint('catalog_version >= 0', name='ck_artifact_run_source_manifest_version'),
        Index('ix_artifact_run_source_manifest_run', 'workspace_id', 'run_id'),
        {'schema': 'artifacts'},
    )
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    project_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(16))
    workspace_id: Mapped[str] = mapped_column(String(128))
    run_id: Mapped[str] = mapped_column(String(128))
    catalog_version: Mapped[int] = mapped_column(BigInteger)


class ArtifactRunSourceModel(Base):
    __tablename__ = 'run_sources'
    __table_args__ = (
        UniqueConstraint('manifest_id', 'source_fingerprint', name='uq_artifact_run_source_fingerprint'),
        ForeignKeyConstraint(['manifest_id'], ['artifacts.run_source_manifests.id'],
            name='fk_artifact_run_source_manifest', ondelete='CASCADE'),
        CheckConstraint("source_fingerprint ~ '^[0-9a-f]{64}$'", name='ck_artifact_run_source_fingerprint'),
        Index('ix_artifact_run_sources_manifest', 'manifest_id', 'id'),
        {'schema': 'artifacts'},
    )
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    manifest_id: Mapped[str] = mapped_column(String(128))
    source_fingerprint: Mapped[str] = mapped_column(String(64))
    source_ref: Mapped[dict] = mapped_column(JSONB)
