from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

UsageBucket = Literal["hour", "day"]
UsageEnvironment = Literal["all", "draft", "staging", "production"]
UsageOperation = Literal["all", "agent", "network"]
UsageGroupBy = Literal[
    "agent",
    "network",
    "model",
    "provider",
    "environment",
    "release",
]
UsageRunType = Literal["agent", "network"]


class ProjectUsageQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_id: UUID
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    bucket: UsageBucket | None = None
    environment: UsageEnvironment = "all"
    operation: UsageOperation = "all"
    network_id: UUID | None = None
    agent_id: UUID | None = None
    provider_model_id: UUID | None = None
    release_id: UUID | None = None
    group_by: UsageGroupBy = "agent"
    top_limit: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def validate_window(self) -> ProjectUsageQuery:
        end = self.to or datetime.now(UTC)
        start = self.from_ or end - timedelta(days=30)
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("from and to must include a UTC offset")
        start = start.astimezone(UTC)
        end = end.astimezone(UTC)
        if start >= end:
            raise ValueError("from must be earlier than to")
        duration = end - start
        if duration > timedelta(days=90):
            raise ValueError("usage range cannot exceed 90 days")
        bucket: UsageBucket = self.bucket or (
            "hour" if duration <= timedelta(hours=48) else "day"
        )
        if bucket == "hour" and duration > timedelta(days=7):
            raise ValueError("hour buckets cannot exceed seven days")
        if self.operation == "agent" and self.group_by == "network":
            self.group_by = "agent"
        self.from_ = start
        self.to = end
        self.bucket = bucket
        return self


class ProjectUsageSummary(BaseModel):
    known_cost_usd: float | None = 0.0
    failed_spend_usd: float = 0.0
    cost_change_percent: float | None = None
    cost_coverage_percent: float | None = None

    agent_runs: int = 0
    direct_agent_runs: int = 0
    network_agent_runs: int = 0
    successful_agent_runs: int = 0
    failed_agent_runs: int = 0
    cancelled_agent_runs: int = 0
    priced_agent_runs: int = 0
    partial_cost_agent_runs: int = 0
    unpriced_agent_runs: int = 0
    agent_run_change_percent: float | None = None
    agent_run_success_rate: float | None = None
    cost_per_priced_agent_run: float | None = None
    median_agent_run_cost_usd: float | None = None
    p95_agent_run_cost_usd: float | None = None

    network_runs: int = 0
    successful_network_runs: int = 0
    failed_network_runs: int = 0
    cancelled_network_runs: int = 0
    priced_network_runs: int = 0
    partial_cost_network_runs: int = 0
    unpriced_network_runs: int = 0
    network_run_change_percent: float | None = None
    network_run_success_rate: float | None = None
    network_run_cost_usd: float | None = 0.0
    cost_per_priced_network_run: float | None = None
    median_network_run_cost_usd: float | None = None
    p95_network_run_cost_usd: float | None = None
    avg_agent_runs_per_network_run: float | None = None

    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    # Transitional aliases for consumers that have not migrated to Run language.
    runtime_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cancelled_requests: int = 0
    priced_requests: int = 0
    partial_cost_requests: int = 0
    unpriced_requests: int = 0
    cost_per_priced_request: float | None = None
    tokens_per_request: float | None = None
    request_change_percent: float | None = None


class ProjectUsageTimeseriesPoint(BaseModel):
    bucket_start: datetime
    agent_runs: int = 0
    direct_agent_runs: int = 0
    network_agent_runs: int = 0
    successful_agent_runs: int = 0
    failed_agent_runs: int = 0
    network_runs: int = 0
    successful_network_runs: int = 0
    failed_network_runs: int = 0
    known_cost_usd: float | None = 0.0
    network_run_cost_usd: float | None = 0.0
    agent_cost_per_run: float | None = None
    network_cost_per_run: float | None = None
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    priced_agent_runs: int = 0
    partial_cost_agent_runs: int = 0
    unpriced_agent_runs: int = 0

    # Transitional aliases.
    runtime_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    priced_requests: int = 0
    partial_cost_requests: int = 0
    unpriced_requests: int = 0


class ProjectUsageComposition(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    embedding_tokens: int = 0
    tool_calls: int = 0
    vector_queries: int = 0


class ProjectUsageBreakdownRow(BaseModel):
    key: str
    label: str
    known_cost_usd: float | None = 0.0
    share_percent: float = 0.0
    agent_runs: int = 0
    network_runs: int = 0
    successful_agent_runs: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_per_priced_agent_run: float | None = None
    cost_coverage_percent: float | None = None

    # Transitional aliases.
    runtime_requests: int = 0
    successful_requests: int = 0
    cost_per_priced_request: float | None = None


class ProjectUsageExecution(BaseModel):
    run_id: UUID
    run_type: UsageRunType
    trace_id: UUID | None = None
    network_id: UUID | None = None
    network_name: str | None = None
    network_execution_id: UUID | None = None
    network_version_id: UUID | None = None
    agent_id: UUID | None = None
    agent_name: str | None = None
    environment: str | None = None
    release_id: UUID | None = None
    release_version: str | None = None
    provider: str | None = None
    model: str | None = None
    status: str
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    agent_runs_count: int = 0
    duration_ms: float | None = None
    known_cost_usd: float | None = None
    cost_status: str
    started_at: datetime | None = None


class ProjectUsageDataQuality(BaseModel):
    fully_priced_agent_runs: int = 0
    partial_agent_runs: int = 0
    unpriced_agent_runs: int = 0
    fully_priced_network_runs: int = 0
    partial_network_runs: int = 0
    unpriced_network_runs: int = 0
    missing_model_attribution: int = 0
    missing_release_attribution: int = 0
    aggregation_lag_seconds: int | None = None

    # Transitional aliases.
    fully_priced_requests: int = 0
    partial_requests: int = 0
    unpriced_requests: int = 0


class ProjectUsageOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_id: UUID
    generated_at: datetime
    data_through: datetime | None = None
    from_: datetime = Field(alias="from")
    to: datetime
    bucket: UsageBucket
    environment: UsageEnvironment
    operation: UsageOperation
    group_by: UsageGroupBy
    summary: ProjectUsageSummary
    timeseries: list[ProjectUsageTimeseriesPoint]
    composition: ProjectUsageComposition
    breakdown: list[ProjectUsageBreakdownRow]
    top_executions: list[ProjectUsageExecution]
    data_quality: ProjectUsageDataQuality
