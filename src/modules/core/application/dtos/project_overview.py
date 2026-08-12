from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

OverviewBucket = Literal["hour", "day"]
OverviewEnvironment = Literal["all", "draft", "staging", "production"]
OverviewTraceEnvironment = Literal["draft", "staging", "production", "playground"]
OverviewRunSource = Literal[
    "playground",
    "api",
    "job",
    "network",
    "event",
    "schedule",
    "unknown",
]
OverviewChangeResource = Literal["agent", "network"]
OverviewChangeAction = Literal[
    "draft_updated",
    "staged",
    "released",
    "rolled_back",
    "reactivated",
]


class ProjectOverviewQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_id: UUID
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    bucket: OverviewBucket | None = None
    environment: OverviewEnvironment = "all"
    recent_limit: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validate_window(self) -> ProjectOverviewQuery:
        end = self.to or datetime.now(UTC)
        start = self.from_ or end - timedelta(hours=24)
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("from and to must include a UTC offset")

        start = start.astimezone(UTC)
        end = end.astimezone(UTC)
        if start >= end:
            raise ValueError("from must be earlier than to")

        duration = end - start
        if duration > timedelta(days=30):
            raise ValueError("overview range cannot exceed 30 days")

        bucket: OverviewBucket = self.bucket or (
            "hour" if duration <= timedelta(hours=48) else "day"
        )
        if bucket == "hour" and duration > timedelta(days=7):
            raise ValueError("hour buckets cannot exceed seven days")

        self.from_ = start
        self.to = end
        self.bucket = bucket
        return self


class ProjectOverviewSummary(BaseModel):
    active_agents: int = 0
    production_agents: int = 0
    network_count: int = 0
    staging_networks: int = 0
    production_networks: int = 0

    agent_runs: int = 0
    direct_agent_runs: int = 0
    network_agent_runs: int = 0
    terminal_agent_runs: int = 0
    successful_agent_runs: int = 0
    completed_with_issues_agent_runs: int = 0
    failed_agent_runs: int = 0
    timed_out_agent_runs: int = 0
    cancelled_agent_runs: int = 0
    running_agent_runs: int = 0
    agent_run_change_percent: float | None = None
    avg_agent_run_duration_ms: float | None = None
    p95_agent_run_duration_ms: float | None = None
    agent_run_success_rate: float | None = None
    agent_run_error_rate: float | None = None
    agent_run_cost_usd: float | None = 0.0
    priced_agent_runs: int = 0
    unknown_agent_run_cost_count: int = 0

    network_runs: int = 0
    terminal_network_runs: int = 0
    successful_network_runs: int = 0
    completed_with_issues_network_runs: int = 0
    failed_network_runs: int = 0
    timed_out_network_runs: int = 0
    uncertain_network_runs: int = 0
    cancelled_network_runs: int = 0
    running_network_runs: int = 0
    network_run_success_rate: float | None = None
    network_run_error_rate: float | None = None
    avg_network_run_duration_ms: float | None = None
    p95_network_run_duration_ms: float | None = None
    avg_agent_runs_per_network_run: float | None = None

    # Deprecated compatibility fields. New consumers must use the Run fields above.
    requests: int = 0
    request_change_percent: float | None = None
    avg_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    success_rate: float | None = None
    failed_requests: int = 0
    cost_usd: float | None = 0.0
    unknown_cost_count: int = 0


class ProjectOverviewTimeseriesPoint(BaseModel):
    bucket_start: datetime

    agent_runs: int = 0
    agent_run_success: int = 0
    agent_run_completed_with_issues: int = 0
    agent_run_failed: int = 0
    agent_run_timed_out: int = 0
    agent_run_cancelled: int = 0
    agent_run_running: int = 0
    agent_run_success_rate: float | None = None
    avg_agent_run_duration_ms: float | None = None
    p95_agent_run_duration_ms: float | None = None

    network_runs: int = 0
    network_run_success: int = 0
    network_run_completed_with_issues: int = 0
    network_run_failed: int = 0
    network_run_timed_out: int = 0
    network_run_uncertain: int = 0
    network_run_cancelled: int = 0
    network_run_running: int = 0
    network_run_success_rate: float | None = None
    avg_network_run_duration_ms: float | None = None

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = 0.0
    unknown_cost_count: int = 0

    # Deprecated compatibility fields.
    requests: int = 0
    success: int = 0
    failed: int = 0
    avg_latency_ms: float | None = None
    p95_latency_ms: float | None = None


class ProjectEnvironmentDistribution(BaseModel):
    draft: int = 0
    staging: int = 0
    production: int = 0

    @property
    def total(self) -> int:
        return self.draft + self.staging + self.production


class ProjectOverviewRelease(BaseModel):
    id: UUID
    agent_id: UUID
    agent_name: str
    version: str
    environment: Literal["draft", "staging", "production"]
    release_notes: str | None = None
    created_at: datetime
    promoted_at: datetime | None = None


class ProjectOverviewNetworkRelease(BaseModel):
    id: UUID
    network_id: UUID
    network_name: str
    version: str
    environment: Literal["staging", "production"]
    change_description: str | None = None
    activation_kind: str | None = None
    rollback_of_version_id: UUID | None = None
    agent_count: int = 0
    created_at: datetime


class ProjectOverviewChange(BaseModel):
    id: UUID
    resource_type: OverviewChangeResource
    resource_id: UUID
    resource_name: str
    environment: Literal["draft", "staging", "production"]
    action: OverviewChangeAction
    version: str | None = None
    revision: int | None = None
    description: str | None = None
    occurred_at: datetime
    immutable: bool


class ProjectOverviewTrace(BaseModel):
    id: UUID
    agent_id: UUID | None = None
    agent_name: str | None = None
    environment: OverviewTraceEnvironment | None = None
    source: OverviewRunSource = "unknown"
    status: str
    latency_ms: float | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    cost_known: bool
    started_at: datetime | None = None


class ProjectOverviewNetworkRun(BaseModel):
    id: UUID
    network_id: UUID
    network_name: str
    environment: Literal["draft", "staging", "production"]
    status: str
    duration_ms: float | None = None
    cost_usd: float | None = None
    cost_known: bool = False
    priced_agent_runs: int = 0
    total_agent_runs: int = 0
    unknown_cost_count: int = 0
    root_trace_id: UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ProjectOverviewIssueEntity(BaseModel):
    entity_id: UUID | None = None
    name: str
    failure_count: int


class ProjectOverviewFailureCode(BaseModel):
    code: str
    failure_count: int


class ProjectOverviewFailurePeak(BaseModel):
    bucket_start: datetime
    failure_count: int


class ProjectOverviewOperationalIssues(BaseModel):
    top_agent_failures: list[ProjectOverviewIssueEntity] = Field(default_factory=list)
    top_network_failures: list[ProjectOverviewIssueEntity] = Field(default_factory=list)
    top_failure_codes: list[ProjectOverviewFailureCode] = Field(default_factory=list)
    failure_peak: ProjectOverviewFailurePeak | None = None


class ProjectKnowledgeSummary(BaseModel):
    collections: int = 0
    documents: int = 0
    indexed_documents: int = 0
    failed_documents: int = 0
    storage_bytes: int = 0
    pending_documents: int = 0


class ProjectToolFailure(BaseModel):
    trace_id: UUID
    tool_name: str
    occurred_at: datetime
    error: str | None = None


class ProjectToolsSummary(BaseModel):
    total: int = 0
    active: int = 0
    inactive: int = 0
    recent_failures: list[ProjectToolFailure] = Field(default_factory=list)


class ProjectOverviewCapabilities(BaseModel):
    sessions_jobs: bool = False
    ingestion_pipeline: bool = False
    activity_feed: bool = False


class ProjectOverviewOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_id: UUID
    generated_at: datetime
    from_: datetime = Field(alias="from")
    to: datetime
    bucket: OverviewBucket
    environment: OverviewEnvironment
    summary: ProjectOverviewSummary
    timeseries: list[ProjectOverviewTimeseriesPoint]
    environment_distribution: ProjectEnvironmentDistribution
    recent_releases: list[ProjectOverviewRelease]
    recent_network_releases: list[ProjectOverviewNetworkRelease] = Field(
        default_factory=list
    )
    recent_changes: list[ProjectOverviewChange] = Field(default_factory=list)
    recent_traces: list[ProjectOverviewTrace]
    recent_network_runs: list[ProjectOverviewNetworkRun] = Field(default_factory=list)
    operational_issues: ProjectOverviewOperationalIssues = Field(
        default_factory=ProjectOverviewOperationalIssues
    )
    knowledge_summary: ProjectKnowledgeSummary
    tools_summary: ProjectToolsSummary
    capabilities: ProjectOverviewCapabilities = Field(
        default_factory=ProjectOverviewCapabilities
    )
