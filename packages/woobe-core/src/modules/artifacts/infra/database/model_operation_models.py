from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import Base


class ArtifactDocumentModelCallModel(Base):
    __tablename__ = 'document_model_calls'
    __table_args__ = (
        UniqueConstraint('job_id', 'operation_key', name='uq_artifact_document_model_operation'),
        ForeignKeyConstraint(['project_id', 'environment', 'workspace_id', 'job_id'],
            ['artifacts.processing_jobs.project_id', 'artifacts.processing_jobs.environment',
             'artifacts.processing_jobs.workspace_id', 'artifacts.processing_jobs.id'], name='fk_artifact_document_model_job'),
        ForeignKeyConstraint(['job_id', 'fencing_token'],
            ['artifacts.processing_attempts.job_id', 'artifacts.processing_attempts.fencing_token'], name='fk_artifact_document_model_attempt'),
        CheckConstraint("operation IN ('summarize','refine_structure')", name='ck_artifact_document_model_operation'),
        CheckConstraint("state IN ('admitted','in_flight','completed','failed','uncertain')", name='ck_artifact_document_model_state'),
        CheckConstraint("input_fingerprint ~ '^[0-9a-f]{64}$' AND binding_fingerprint ~ '^[0-9a-f]{64}$'", name='ck_artifact_document_model_digests'),
        CheckConstraint('fencing_token >= 1 AND budget_tokens >= 0 AND max_output_tokens >= 1 AND max_output_tokens <= 32768 AND observation_revision >= 0', name='ck_artifact_document_model_bounds'),
        CheckConstraint('(input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0) AND (cost_usd IS NULL OR cost_usd >= 0)', name='ck_artifact_document_model_usage'),
        CheckConstraint("cost_status IN ('reported','estimated','unknown')", name='ck_artifact_document_model_cost_status'),
        CheckConstraint("(state = 'completed' AND response IS NOT NULL AND response_sha256 ~ '^[0-9a-f]{64}$') OR (state <> 'completed' AND response IS NULL AND response_sha256 IS NULL)", name='ck_artifact_document_model_result'),
        CheckConstraint('response IS NULL OR octet_length(response::text) <= 262144', name='ck_artifact_document_model_response_bound'),
        Index('ix_artifact_document_model_job_budget', 'job_id', 'state'),
        {'schema': 'artifacts'},
    )
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    project_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(16))
    workspace_id: Mapped[str] = mapped_column(String(128))
    job_id: Mapped[str] = mapped_column(String(128))
    operation_key: Mapped[str] = mapped_column(String(128))
    operation: Mapped[str] = mapped_column(String(32))
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    binding_fingerprint: Mapped[str] = mapped_column(String(64))
    fencing_token: Mapped[int] = mapped_column(BigInteger)
    nonce: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(16), default='admitted')
    budget_tokens: Mapped[int] = mapped_column(BigInteger)
    max_output_tokens: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    cost_status: Mapped[str] = mapped_column(String(16), default='unknown')
    provider_request_id: Mapped[str | None] = mapped_column(String(255))
    response: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    response_sha256: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observation_revision: Mapped[int] = mapped_column(Integer, default=0)
