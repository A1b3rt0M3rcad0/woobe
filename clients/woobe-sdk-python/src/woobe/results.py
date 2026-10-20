from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from woobe.events import WoobeEvent


class Usage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None


class Source(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    document_title: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    page_number: int | None = None
    score: float | None = None
    content_preview: str | None = None


class ToolCall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    tool_call_id: str | None = None
    tool_name: str | None = None
    input: Any = None
    output: Any = None
    duration_ms: float | None = None
    success: bool | None = None
    status: str | None = None
    latency_ms: float | None = None
    error: str | None = None
    error_code: str | None = None


class FallbackInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    primary_model: str | None = None
    primary_provider: str | None = None
    primary_provider_model_id: str | None = None
    primary_credential_id: str | None = None
    primary_error: str | None = None
    fallback_model: str | None = None
    fallback_provider: str | None = None
    fallback_provider_model_id: str | None = None
    fallback_credential_id: str | None = None


class ExecutionEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    schema_version: int | None = None
    event_id: str | None = None
    trace_id: str | None = None
    root_span_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    sequence: int | None = None
    event_type: str | None = None
    phase: str | None = None
    status: str | None = None
    occurred_at: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ExecutionDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    schema_version: int | None = None

    agent_runtime_latency_ms: float | None = None
    total_latency_ms: float | None = None
    prepare_latency_ms: float | None = None
    llm_work_latency_ms: float | None = None
    llm_runtime_latency_ms: float | None = None

    tool_wall_latency_ms: float | None = None
    tool_work_latency_ms: float | None = None
    tool_call_duration_sum_ms: float | None = None
    tool_parallelism_ratio: float | None = None
    tool_provider_work_ms: float | None = None
    tool_runtime_overhead_ms: float | None = None
    tool_http_latency_ms: float | None = None
    tool_overhead_latency_ms: float | None = None
    tool_share_percent: float | None = None

    finalization_work_latency_ms: float | None = None
    persistence_latency_ms: float | None = None
    other_latency_ms: float | None = None
    unaccounted_latency_ms: float | None = None
    orchestration_latency_ms: float | None = None

    llm_call_count: int | None = None
    tool_call_count: int | None = None
    successful_tool_calls: int | None = None
    failed_tool_calls: int | None = None

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    usage_complete: bool | None = None
    cost_status: str | None = None
    cost_reason: str | None = None
    cost_statuses: list[str] = Field(default_factory=list)
    pricing_ids: list[str] = Field(default_factory=list)

    source_count: int | None = None
    answer_length: int | None = None
    structured_output: bool | None = None

    provider: str | None = None
    model: str | None = None
    provider_model_id: str | None = None
    provider_credential_id: str | None = None
    fallback_provider_model_id: str | None = None
    fallback_credential_id: str | None = None
    fallback_used: bool | None = None

    execution_context: str | None = None
    execution_strategy: str | None = None
    agent_release_id: str | None = None
    agent_release_version: str | None = None

    notes: list[str] = Field(default_factory=list)


class ChatResult(BaseModel):
    """Typed terminal result captured from a completed Runtime event."""

    model_config = ConfigDict(frozen=True, extra="allow")

    run_id: str
    session_id: str
    run_kind: str
    terminal_event_type: str

    answer: str = ""
    message_id: str | None = None
    trace_id: str | None = None

    usage: Usage | None = None
    sources: list[Source] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)

    model: str | None = None
    provider: str | None = None
    provider_model_id: str | None = None
    provider_credential_id: str | None = None
    fallback_provider_model_id: str | None = None
    fallback_credential_id: str | None = None

    fallback_used: bool = False
    fallback_info: FallbackInfo | None = None

    latency_ms: float | None = None
    ttft_ms: float | None = None

    parsed_output: Any = None
    output_parse_error: str | None = None

    execution_events: list[ExecutionEvent] = Field(default_factory=list)
    diagnostics: ExecutionDiagnostics | None = None

    @classmethod
    def from_event(cls, event: WoobeEvent) -> ChatResult:
        payload = dict(event.payload)

        answer = payload.get("answer")
        if not isinstance(answer, str):
            output = payload.get("output")
            answer = output if isinstance(output, str) else ""

        payload["run_id"] = event.run_id
        payload["session_id"] = event.session_id
        payload["run_kind"] = event.run_kind
        payload["terminal_event_type"] = event.type
        payload["answer"] = answer

        return cls.model_validate(payload)

    @property
    def agent_release_id(self) -> str | None:
        return self.diagnostics.agent_release_id if self.diagnostics is not None else None

    @property
    def agent_release_version(self) -> str | None:
        return self.diagnostics.agent_release_version if self.diagnostics is not None else None

    @property
    def execution_context(self) -> str | None:
        return self.diagnostics.execution_context if self.diagnostics is not None else None

    @property
    def execution_strategy(self) -> str | None:
        return self.diagnostics.execution_strategy if self.diagnostics is not None else None
