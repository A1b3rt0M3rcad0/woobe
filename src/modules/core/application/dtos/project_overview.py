from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

OverviewBucket = Literal["hour", "day"]
OverviewEnvironment = Literal["all", "draft", "staging", "production"]


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
    requests: int = 0
    success: int = 0
    failed: int = 0
    avg_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = 0.0
    unknown_cost_count: int = 0


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
    created_at: datetime
    promoted_at: datetime | None = None


class ProjectOverviewTrace(BaseModel):
    id: UUID
    agent_id: UUID | None = None
    agent_name: str | None = None
    environment: Literal["draft", "staging", "production"] | None = None
    status: str
    latency_ms: float | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    cost_known: bool
    started_at: datetime | None = None


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
    recent_traces: list[ProjectOverviewTrace]
    knowledge_summary: ProjectKnowledgeSummary
    tools_summary: ProjectToolsSummary
    capabilities: ProjectOverviewCapabilities = Field(
        default_factory=ProjectOverviewCapabilities
    )
