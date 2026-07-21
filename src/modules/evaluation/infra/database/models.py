from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel


class EvaluationDatasetModel(BaseModel):
    __tablename__ = "datasets"
    __table_args__ = (
        Index("ix_evaluation_datasets_project_status", "project_id", "status", "updated_at"),
        Index("uq_evaluation_datasets_project_name", "project_id", text("lower(btrim(name))"), unique=True),
        {"schema": "evaluation"},
    )

    project_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active")
    current_version_id: Mapped[UUID | None]
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[UUID | None]
    created_by: Mapped[UUID | None]


class EvaluationDatasetVersionModel(BaseModel):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version", name="uq_evaluation_dataset_versions_version"),
        Index("ix_evaluation_dataset_versions_project_created", "project_id", "created_at"),
        Index("ix_evaluation_dataset_versions_source_snapshot", "project_id", "source_snapshot_hash"),
        {"schema": "evaluation"},
    )

    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.datasets.id"))
    project_id: Mapped[UUID]
    version: Mapped[str] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64))
    change_description: Mapped[str | None] = mapped_column(Text)
    authoring_source: Mapped[str] = mapped_column(String(32), default="manual")
    source_snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    source_context_hash: Mapped[str | None] = mapped_column(String(64))
    authoring_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[UUID | None]
    created_by: Mapped[UUID | None]


class EvaluationTestCaseModel(BaseModel):
    __tablename__ = "test_cases"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "position", name="uq_evaluation_test_cases_position"),
        Index("ix_evaluation_test_cases_version", "dataset_version_id", "position"),
        CheckConstraint("weight > 0", name="ck_evaluation_test_cases_weight"),
        CheckConstraint(
            "production_frequency IS NULL OR (production_frequency >= 0 AND production_frequency <= 1)",
            name="ck_evaluation_test_cases_frequency",
        ),
        CheckConstraint(
            "case_type IN ('success', 'refusal', 'handled_error', 'expected_failure')",
            name="ck_evaluation_test_cases_case_type",
        ),
        {"schema": "evaluation"},
    )

    dataset_version_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.dataset_versions.id"))
    project_id: Mapped[UUID]
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    case_type: Mapped[str] = mapped_column(String(32), default="success")
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    initial_context: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    expected_contract: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    severity: Mapped[str] = mapped_column(String(32), default="normal")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    blocking: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    production_frequency: Mapped[float | None] = mapped_column(Float)


class EvaluationSuiteModel(BaseModel):
    __tablename__ = "suites"
    __table_args__ = (
        Index("ix_evaluation_suites_project_status", "project_id", "status", "updated_at"),
        Index("uq_evaluation_suites_project_name", "project_id", text("lower(btrim(name))"), unique=True),
        {"schema": "evaluation"},
    )

    project_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    target_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="active")
    current_version_id: Mapped[UUID | None]
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[UUID | None]
    created_by: Mapped[UUID | None]


class EvaluationSuiteVersionModel(BaseModel):
    __tablename__ = "suite_versions"
    __table_args__ = (
        UniqueConstraint("suite_id", "version", name="uq_evaluation_suite_versions_version"),
        Index("ix_evaluation_suite_versions_project_created", "project_id", "created_at"),
        {"schema": "evaluation"},
    )

    suite_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.suites.id"))
    project_id: Mapped[UUID]
    version: Mapped[str] = mapped_column(String(64))
    parent_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("evaluation.suite_versions.id"))
    change_description: Mapped[str | None] = mapped_column(Text)
    dataset_version_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.dataset_versions.id"))
    judge_provider_model_id: Mapped[UUID]
    judge_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    rubric: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    deterministic_checks: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    acceptance_policy: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    repetition_policy: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    estimate_defaults: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    suite_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[UUID | None]


class EvaluationRunModel(BaseModel):
    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_evaluation_runs_project_created", "project_id", "created_at"),
        Index("ix_evaluation_runs_status_created", "status", "created_at"),
        Index(
            "uq_evaluation_runs_project_idempotency",
            "project_id",
            "request_idempotency_key",
            unique=True,
            postgresql_where=text("request_idempotency_key IS NOT NULL"),
        ),
        CheckConstraint("repetitions BETWEEN 1 AND 25", name="ck_evaluation_runs_repetitions"),
        {"schema": "evaluation"},
    )

    project_id: Mapped[UUID]
    suite_version_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.suite_versions.id"))
    mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    repetitions: Mapped[int] = mapped_column(Integer, default=1)
    execution_order: Mapped[str] = mapped_column(String(32), default="paired_interleaved")
    execution_policy: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    randomization_seed: Mapped[int] = mapped_column(Integer)
    request_idempotency_key: Mapped[str | None] = mapped_column(String(255))
    candidate_target_id: Mapped[UUID | None]
    baseline_target_id: Mapped[UUID | None]
    parent_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("evaluation.runs.id"), nullable=True)
    requested_by: Mapped[UUID | None]
    qualification_status: Mapped[str | None] = mapped_column(String(64))
    overall_score: Mapped[float | None] = mapped_column(Float)
    pass_rate: Mapped[float | None] = mapped_column(Float)
    aggregate_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    failure_code: Mapped[str | None] = mapped_column(String(128))
    failure_detail: Mapped[str | None] = mapped_column(Text)
    estimated_preflight_cost: Mapped[float | None] = mapped_column(Numeric(18, 10))
    measured_total_cost: Mapped[float | None] = mapped_column(Numeric(18, 10))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationTargetModel(BaseModel):
    __tablename__ = "targets"
    __table_args__ = (
        UniqueConstraint("evaluation_run_id", "side", name="uq_evaluation_targets_run_side"),
        Index("ix_evaluation_targets_entity", "project_id", "target_type", "entity_id"),
        Index("ix_evaluation_targets_snapshot_hash", "project_id", "snapshot_hash"),
        {"schema": "evaluation"},
    )

    evaluation_run_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.runs.id"))
    project_id: Mapped[UUID]
    side: Mapped[str] = mapped_column(String(32))
    target_type: Mapped[str] = mapped_column(String(32))
    source_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(32))
    agent_release_id: Mapped[UUID | None]
    network_version_id: Mapped[UUID | None]
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    composition_hash: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(255))
    display_version: Mapped[str] = mapped_column(String(128))


class EvaluationTrialModel(BaseModel):
    __tablename__ = "trials"
    __table_args__ = (
        UniqueConstraint("evaluation_run_id", "evaluation_target_id", "test_case_id", "repetition", name="uq_evaluation_trials_identity"),
        Index("ix_evaluation_trials_run_status", "evaluation_run_id", "status", "created_at"),
        Index("ix_evaluation_trials_pair", "evaluation_run_id", "pair_key"),
        {"schema": "evaluation"},
    )

    evaluation_run_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.runs.id"))
    evaluation_target_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.targets.id"))
    test_case_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.test_cases.id"))
    project_id: Mapped[UUID]
    repetition: Mapped[int] = mapped_column(Integer)
    pair_key: Mapped[str] = mapped_column(String(255))
    execution_order: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    agent_run_id: Mapped[UUID | None]
    network_execution_id: Mapped[UUID | None]
    root_trace_id: Mapped[UUID | None]
    output_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    observed_outcome: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    failure_origin: Mapped[str | None] = mapped_column(String(32))
    failure_stage: Mapped[str | None] = mapped_column(String(32))
    score: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool | None]
    failure_code: Mapped[str | None] = mapped_column(String(128))
    failure_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    runtime_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    judge_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    judge_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationCheckResultModel(BaseModel):
    __tablename__ = "check_results"
    __table_args__ = (
        UniqueConstraint("evaluation_trial_id", "evaluator_type", "evaluator_key", name="uq_evaluation_check_results_identity"),
        Index("ix_evaluation_check_results_trial", "evaluation_trial_id", "created_at"),
        {"schema": "evaluation"},
    )

    evaluation_trial_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.trials.id"))
    project_id: Mapped[UUID]
    evaluator_key: Mapped[str] = mapped_column(String(128))
    evaluator_type: Mapped[str] = mapped_column(String(32))
    dimension: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32))
    score: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    blocking: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class EvaluatorModelCallModel(BaseModel):
    __tablename__ = "model_calls"
    __table_args__ = (
        UniqueConstraint("evaluation_trial_id", name="uq_evaluation_model_calls_trial"),
        Index("ix_evaluation_model_calls_run", "evaluation_run_id", "created_at"),
        Index("ix_evaluation_model_calls_trial", "evaluation_trial_id"),
        {"schema": "evaluation"},
    )

    evaluation_run_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.runs.id"))
    evaluation_trial_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.trials.id"))
    project_id: Mapped[UUID]
    provider_model_id: Mapped[UUID]
    provider_credential_id: Mapped[UUID]
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(255))
    judge_config_hash: Mapped[str] = mapped_column(String(64))
    rubric_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(18, 10))
    cost_status: Mapped[str | None] = mapped_column(String(32))
    cost_reason: Mapped[str | None] = mapped_column(Text)
    pricing_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    structured_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationAuthoringCallModel(BaseModel):
    __tablename__ = "authoring_calls"
    __table_args__ = (
        Index("ix_evaluation_authoring_calls_project_created", "project_id", "created_at"),
        Index("ix_evaluation_authoring_calls_snapshot", "project_id", "target_snapshot_hash"),
        Index("ix_evaluation_authoring_calls_status", "status", "created_at"),
        CheckConstraint("requested_case_count BETWEEN 1 AND 100", name="ck_evaluation_authoring_case_count"),
        {"schema": "evaluation"},
    )

    project_id: Mapped[UUID]
    target_type: Mapped[str] = mapped_column(String(32))
    target_entity_id: Mapped[UUID]
    target_source_type: Mapped[str] = mapped_column(String(32))
    target_version_id: Mapped[UUID | None]
    target_snapshot_hash: Mapped[str] = mapped_column(String(64))
    generator_provider_model_id: Mapped[UUID]
    generator_provider_credential_id: Mapped[UUID]
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(255))
    objective: Mapped[str] = mapped_column(Text)
    requested_case_count: Mapped[int] = mapped_column(Integer)
    coverage_request: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32))
    prompt_version: Mapped[str] = mapped_column(String(64), default="suite-generator-v1")
    context_hash: Mapped[str] = mapped_column(String(64))
    context_stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    context_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    total_batch_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_batch_count: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(18, 10))
    pricing_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    generated_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    validation_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None]
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationAuthoringBatchModel(BaseModel):
    __tablename__ = "authoring_batches"
    __table_args__ = (
        UniqueConstraint("authoring_call_id", "batch_index", name="uq_evaluation_authoring_batches_index"),
        CheckConstraint("requested_case_count BETWEEN 1 AND 10", name="ck_evaluation_authoring_batch_case_count"),
        Index("ix_evaluation_authoring_batches_call_status", "authoring_call_id", "status", "batch_index"),
        Index("ix_evaluation_authoring_batches_project_created", "project_id", "created_at"),
        {"schema": "evaluation"},
    )

    authoring_call_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.authoring_calls.id"))
    project_id: Mapped[UUID]
    batch_index: Mapped[int] = mapped_column(Integer)
    requested_case_count: Mapped[int] = mapped_column(Integer)
    coverage_request: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(18, 10))
    pricing_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    generated_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    validation_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EstimateRunModel(BaseModel):
    __tablename__ = "estimate_runs"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_run_id",
            "target_id",
            "volume",
            "volume_unit",
            "price_snapshot_hash",
            name="uq_evaluation_estimates_run_target_volume_price",
        ),
        Index("ix_evaluation_estimates_run", "evaluation_run_id", "created_at"),
        {"schema": "evaluation"},
    )

    project_id: Mapped[UUID]
    evaluation_run_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.runs.id"))
    target_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.targets.id"))
    volume_unit: Mapped[str] = mapped_column(String(64), default="runs_per_month")
    volume: Mapped[int] = mapped_column(Integer)
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    observation_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    price_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    price_snapshot_hash: Mapped[str] = mapped_column(String(64), default="none")
    scenarios: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[str] = mapped_column(String(32))
    limitations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_by: Mapped[UUID | None]


class ReleaseQualificationModel(BaseModel):
    __tablename__ = "release_qualifications"
    __table_args__ = (
        UniqueConstraint("evaluation_run_id", "target_snapshot_hash", name="uq_evaluation_qualification_run_target"),
        Index("ix_evaluation_qualifications_target", "project_id", "target_type", "entity_id", "created_at"),
        Index("ix_evaluation_qualifications_snapshot", "project_id", "target_snapshot_hash"),
        {"schema": "evaluation"},
    )

    project_id: Mapped[UUID]
    target_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[UUID]
    target_snapshot_hash: Mapped[str] = mapped_column(String(64))
    agent_release_id: Mapped[UUID | None]
    network_version_id: Mapped[UUID | None]
    suite_version_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.suite_versions.id"))
    dataset_version_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.dataset_versions.id"))
    evaluation_run_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.runs.id"))
    status: Mapped[str] = mapped_column(String(64))
    score: Mapped[float | None] = mapped_column(Float)
    pass_rate: Mapped[float | None] = mapped_column(Float)
    critical_failures: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
