from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from modules.agent.application.interfaces.execution import InstrumentedExecution


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RequestExecutionContext:
    started_at: float
    request_received_at: str
    execution_started_at: str
    client_sent_at: str | None = None
    run_id: UUID | None = None
    terminal_persisted: bool = False
    project_id: UUID | None = None
    agent_id: UUID | None = None
    session_id: UUID | None = None
    input_message_id: UUID | None = None
    output_message_id: UUID | None = None
    intermediate_messages: list[dict[str, Any]] | None = None
    trace_id: UUID | None = None
    prepare_started_at: str | None = None
    prepare_ended_at: str | None = None
    prepare_latency_ms: int = 0
    strict_json: bool = False
    execution: InstrumentedExecution | None = None
    execution_context: str | None = None
    execution_strategy: str | None = None
    agent_release_id: UUID | None = None
    agent_release_version: str | None = None
    rag_metadata: dict[str, Any] | None = None
    tool_snapshots: dict[str, dict[str, Any]] | None = None
    tool_metadata: dict[str, Any] | None = None
    persisted_sources: list[Any] | None = None
    network_id: UUID | None = None
    network_version_id: UUID | None = None
    network_session_id: UUID | None = None
    network_execution_id: UUID | None = None
    network_invocation_id: UUID | None = None
    parent_invocation_id: UUID | None = None
    network_node_id: UUID | None = None
    depth: int | None = None
    tool_result_max_chars: int | None = None
    internal_tool_definitions: list[dict[str, Any]] | None = None
    internal_tool_name_to_id: dict[str, str] | None = None
    internal_tool_handlers: dict[
        UUID,
        Callable[[dict], Awaitable[dict]],
    ] | None = None

    # External Context is resolved at Acceptance and frozen for the Run. Only
    # explicitly exposed fields are copied into model_external_context.
    external_context_contract: dict[str, Any] | None = None
    external_context_snapshot: dict[str, Any] | None = None
    model_external_context: dict[str, Any] | None = None

    # Durable Run journal state. The recorder is runtime-only and is never serialized.
    storage_version: str = "legacy_v1"
    run_attempt: int = 1
    run_event_recorder: Any | None = None
    resume_state: dict[str, Any] | None = None

    # Run-local procedural content, never serialized as Session history.
    skill_context: list[dict[str, Any]] | None = None

    # Context Engineering evidence. These values are configuration/provenance only;
    # raw secrets and full materialized prompts must never be stored here.
    context_policy: dict[str, Any] | None = None
    context_assembler_name: str | None = None
    context_assembler_version: str | None = None
    context_assembler_strategy_name: str | None = None
    context_assembler_strategy_version: str | None = None
    model_capacity_units: int | None = None
    reserved_output_units: int | None = None
    active_tool_definitions: list[dict[str, Any]] | None = None
    context_selection_metadata: dict[str, Any] | None = None
    context_rag_sources: list[dict[str, Any]] | None = None

    # Ephemeral preparation material. Project Environment secrets remain encrypted
    # here and are materialized only at the Tool invocation boundary. Nothing in
    # this section may be serialized to Redis or durable snapshots.
    prepared_fallback: dict[str, Any] | None = None
    prepared_tools: dict[str, Any] | None = None
    prepared_tool_secrets: dict[str, str] | None = None
    prepared_project_environment: dict[str, Any] | None = None
    prepared_rag: dict[str, Any] | None = None


current_execution: ContextVar[RequestExecutionContext | None] = ContextVar(
    "current_agent_execution",
    default=None,
)


def new_execution_context(
    request_received_at: str | None = None,
    client_sent_at: str | None = None,
) -> RequestExecutionContext:
    now = utc_now()
    return RequestExecutionContext(
        started_at=time.monotonic(),
        request_received_at=request_received_at or now,
        execution_started_at=now,
        client_sent_at=client_sent_at,
    )
