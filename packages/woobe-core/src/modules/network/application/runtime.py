from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol
from uuid import UUID, uuid5

from modules.network.application.runtime_failures import (
    NetworkRuntimeFailure,
    classify_runtime_exception,
)
from modules.network.domain.entities import NetworkDefinition, NetworkNode
from modules.network.domain.graph import delegation_tool_name


NETWORK_TOOL_NAMESPACE = UUID("bd84d8e4-0d63-4a8f-96ca-3fd22e42dfe0")
AgentStreamHandler = Callable[[str, dict[str, Any]], Awaitable[None]]
_VALID_AGENT_SESSION_MODES = {"stateful", "stateless"}


@dataclass(frozen=True, slots=True)
class NetworkExecutionSnapshot:
    id: UUID
    network_id: UUID
    network_version_id: UUID | None
    network_session_id: UUID
    project_id: UUID
    input_message: str
    draft_revision: int | None
    definition_snapshot: dict[str, Any] | None
    resolved_bindings_snapshot: dict[str, Any] | None
    status: str


@dataclass(frozen=True, slots=True)
class NetworkVersionSnapshot:
    id: UUID
    kind: str
    definition: dict[str, Any]
    resolved_bindings: dict[str, Any]
    version: str | None = None


@dataclass(frozen=True, slots=True)
class NetworkInvocationState:
    id: UUID
    network_execution_id: UUID
    network_session_id: UUID
    parent_invocation_id: UUID | None
    node_id: UUID
    agent_id: UUID
    agent_session_id: UUID | None
    trace_id: UUID | None
    depth: int
    status: str
    input_message: str
    context_state: str = "stateless"
    previous_invocation_count: int = 0


def agent_capability_summary(node: NetworkNode) -> str:
    capability = " ".join(node.capability_description.split())
    return capability or f"This specialist performs the role represented by {node.label}."


def delegation_tool_description(node: NetworkNode) -> str:
    capability = agent_capability_summary(node)
    return (
        f"Delegate a focused task to {node.label}. "
        f"Specialist capability: {capability} "
        "Use this specialist only when that capability is required. Send the "
        "precise task and only the context needed to complete it, then integrate "
        "the returned result into your response. This runtime Tool is the source "
        "of truth for whether this Agent can be delegated to; never claim a "
        "delegation occurred unless the Tool actually completed successfully. "
        "If the runtime reports network_deadline_near, stop delegating and produce "
        "the best final response from results already available."
    )


def _delegation_fingerprint(
    *,
    target_node_id: UUID,
    task: str,
    context: object,
    expected_output: str,
) -> str:
    normalized_task = " ".join(task.lower().split())
    normalized_expected = " ".join(expected_output.lower().split())
    payload = {
        "target_node_id": str(target_node_id),
        "task": normalized_task,
        "context": context if isinstance(context, dict) else None,
        "expected_output": normalized_expected,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class NetworkBudgetExceeded(RuntimeError):
    def __init__(self, message: str, *, code: str = "network_budget_exceeded") -> None:
        super().__init__(message)
        self.code = code


class NetworkExecutionCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentInvocationResult:
    answer: str
    session_id: UUID | None = None
    trace_id: UUID | None = None
    provider: str | None = None
    model: str | None = None
    usage: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    sources: list[dict[str, Any]] | None = None
    parsed_output: dict[str, Any] | None = None
    output_parse_error: str | None = None
    execution_events: list[dict[str, Any]] | None = None
    streamed_output: bool = False


@dataclass
class InternalDelegationTool:
    id: UUID
    name: str
    description: str
    handler: Callable[[dict], Awaitable[dict]]

    def definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The precise task the specialist must complete.",
                        },
                        "context": {
                            "type": "object",
                            "description": "Only the context required to complete the task.",
                            "additionalProperties": True,
                        },
                        "expected_output": {
                            "type": "string",
                            "description": (
                                "Optional description of the result the specialist "
                                "should return."
                            ),
                        },
                    },
                    "required": ["task"],
                    "additionalProperties": False,
                },
            },
        }


class AgentInvoker(Protocol):
    async def invoke(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        release_id: UUID | None,
        snapshot_override: dict[str, Any] | None,
        message: str,
        agent_session_id: UUID | None,
        execution_context: str,
        internal_tools: list[InternalDelegationTool],
        network_context: dict[str, object],
        stream_handler: AgentStreamHandler | None = None,
    ) -> AgentInvocationResult: ...


class NetworkExecutionStore(Protocol):
    async def is_cancel_requested(self, execution_id: UUID) -> bool: ...

    async def start_invocation(
        self,
        *,
        execution: NetworkExecutionSnapshot,
        node_id: UUID,
        agent_id: UUID,
        depth: int,
        message: str,
        parent_invocation_id: UUID | None,
        persist_context: bool,
    ) -> NetworkInvocationState: ...

    async def complete_invocation(
        self,
        invocation_id: UUID,
        *,
        result: AgentInvocationResult,
        persist_context: bool,
    ) -> None: ...

    async def fail_invocation(
        self,
        invocation_id: UUID,
        error: str,
        *,
        trace_id: UUID | None = None,
        agent_session_id: UUID | None = None,
        persist_context: bool = False,
    ) -> None: ...

    async def emit(
        self,
        execution_id: UUID,
        event_type: str,
        payload: dict,
        *,
        invocation_id: UUID | None = None,
    ) -> None: ...


def _preparation_failure(
    exception: Exception,
    *,
    code: str,
    stage: str,
    message: str,
    node: NetworkNode,
    invocation_id: UUID | None = None,
) -> NetworkRuntimeFailure:
    classified = classify_runtime_exception(exception, stage=stage)
    return NetworkRuntimeFailure(
        code=code,
        stage=stage,
        safe_message=message,
        internal_detail=classified.internal_detail,
        retryable=False,
        invocation_id=invocation_id,
        node_id=node.id,
        agent_id=node.agent_id,
        trace_id=classified.trace_id,
        agent_session_id=classified.agent_session_id,
        phase=classified.phase,
        call_index=classified.call_index,
        upstream_status=classified.upstream_status,
        upstream_error_code=classified.upstream_error_code,
        partial_result_available=classified.partial_result_available,
    )


class NetworkExecutor:
    def __init__(self, *, invoker: AgentInvoker, store: NetworkExecutionStore) -> None:
        self._invoker = invoker
        self._store = store

    async def execute(
        self,
        execution: NetworkExecutionSnapshot,
        version: NetworkVersionSnapshot | None,
    ) -> AgentInvocationResult:
        if version is None:
            if not execution.definition_snapshot or not execution.resolved_bindings_snapshot:
                raise RuntimeError("Draft execution snapshot is missing")
            definition_payload = execution.definition_snapshot
            resolved_bindings = execution.resolved_bindings_snapshot
            runtime_environment = "draft"
        else:
            definition_payload = version.definition
            resolved_bindings = version.resolved_bindings
            runtime_environment = "production" if version.kind == "release" else "staging"

        definition = NetworkDefinition.from_dict(definition_payload)
        nodes = {node.id: node for node in definition.nodes}
        outgoing: dict[UUID, list[UUID]] = {node_id: [] for node_id in nodes}
        for edge in definition.edges:
            outgoing[edge.source_node_id].append(edge.target_node_id)

        timeout_seconds = float(definition.limits.timeout_seconds)
        started = time.monotonic()
        deadline = started + timeout_seconds
        # Keep enough of the configured wall clock for the parent Agent to consume
        # completed Tool/delegation results and make its terminal model call. This is
        # deliberately an internal policy, not another MVP setting users must tune.
        finalization_reserve_seconds = min(
            15.0,
            max(2.0, timeout_seconds * 0.15),
        )
        invocation_count = 0
        count_lock = asyncio.Lock()

        def remaining_seconds() -> float:
            return max(0.0, deadline - time.monotonic())

        async def invoke_node(
            node_id: UUID,
            message: str,
            depth: int,
            parent_invocation_id: UUID | None,
        ) -> AgentInvocationResult:
            nonlocal invocation_count
            if await self._store.is_cancel_requested(execution.id):
                raise NetworkExecutionCancelled("Network execution was cancelled")
            if depth > definition.limits.max_depth:
                raise NetworkBudgetExceeded(
                    "Network maximum depth exceeded",
                    code="network_max_depth_exceeded",
                )
            if remaining_seconds() <= 0:
                raise NetworkBudgetExceeded(
                    "Network execution timeout exceeded",
                    code="network_timeout_exceeded",
                )
            async with count_lock:
                invocation_count += 1
                if invocation_count > definition.limits.max_invocations:
                    raise NetworkBudgetExceeded(
                        "Network invocation budget exceeded",
                        code="network_max_invocations_exceeded",
                    )

            node = nodes[node_id]
            binding = resolved_bindings.get(str(node_id)) or {}
            release_id = binding.get("release_id")
            release_uuid = UUID(str(release_id)) if release_id else None
            snapshot_override = binding.get("snapshot_override")

            if runtime_environment == "draft" and not isinstance(snapshot_override, dict):
                raise _preparation_failure(
                    RuntimeError(f"Node {node_id} has no Agent Draft snapshot"),
                    code="agent_binding_error",
                    stage="agent_binding_resolution",
                    message="The Agent Draft snapshot could not be resolved for this Network Run.",
                    node=node,
                )
            if runtime_environment != "draft" and release_uuid is None:
                raise _preparation_failure(
                    RuntimeError(f"Node {node_id} has no immutable Agent release binding"),
                    code="agent_binding_error",
                    stage="agent_binding_resolution",
                    message="The Agent snapshot pinned by this Network Version could not be resolved.",
                    node=node,
                )

            raw_session_mode = binding.get("session_mode")
            agent_session_mode = str(raw_session_mode) if raw_session_mode is not None else ""
            if agent_session_mode not in _VALID_AGENT_SESSION_MODES:
                raise _preparation_failure(
                    RuntimeError(f"Node {node_id} has no frozen Agent Session Mode"),
                    code="agent_binding_error",
                    stage="agent_binding_resolution",
                    message="The Agent Session Mode pinned by this Network Version could not be resolved.",
                    node=node,
                )

            persist_agent_context = (
                definition.session_mode == "stateful"
                and agent_session_mode == "stateful"
            )
            try:
                invocation = await self._store.start_invocation(
                    execution=execution,
                    node_id=node.id,
                    agent_id=node.agent_id,
                    depth=depth,
                    message=message,
                    parent_invocation_id=parent_invocation_id,
                    persist_context=persist_agent_context,
                )
            except Exception as exc:
                raise _preparation_failure(
                    exc,
                    code="agent_context_error",
                    stage="agent_context_preparation",
                    message="The Agent runtime context could not be prepared for this Network Run.",
                    node=node,
                ) from exc

            invocation_context_state = str(
                getattr(
                    invocation,
                    "context_state",
                    "created" if persist_agent_context else "stateless",
                )
            )
            previous_invocation_count = int(
                getattr(invocation, "previous_invocation_count", 0) or 0
            )
            try:
                await self._store.emit(
                    execution.id,
                    "agent_invocation_started",
                    {
                        "label": node.label,
                        "invocation_count": invocation_count,
                        "provider": (
                            snapshot_override.get("provider")
                            if isinstance(snapshot_override, dict)
                            else None
                        ),
                        "model": (
                            snapshot_override.get("model")
                            if isinstance(snapshot_override, dict)
                            else None
                        ),
                        "session_mode": agent_session_mode,
                        "agent_session_id": (
                            str(invocation.agent_session_id)
                            if invocation.agent_session_id
                            else None
                        ),
                        "context_state": invocation_context_state,
                        "previous_invocation_count": previous_invocation_count,
                        "source": (
                            "draft"
                            if runtime_environment == "draft"
                            else "release"
                            if runtime_environment == "production"
                            else "staging"
                        ),
                        "version": (
                            f"r{execution.draft_revision}"
                            if runtime_environment == "draft"
                            else binding.get("release_version")
                        ),
                    },
                    invocation_id=invocation.id,
                )
            except Exception as exc:
                await self._store.fail_invocation(invocation.id, str(exc))
                raise _preparation_failure(
                    exc,
                    code="agent_context_error",
                    stage="agent_invocation_start",
                    message="The Agent invocation could not be started for this Network Run.",
                    node=node,
                    invocation_id=invocation.id,
                ) from exc

            tools: list[InternalDelegationTool] = []
            active_delegation_fingerprints: set[str] = set()
            successful_delegation_targets: set[UUID] = set()
            for target_id in outgoing[node_id]:
                target = nodes[target_id]
                tool_id = uuid5(
                    NETWORK_TOOL_NAMESPACE,
                    f"{execution.id}:{node_id}:{target_id}",
                )

                async def delegate(
                    arguments: dict,
                    *,
                    delegated_target_id: UUID = target_id,
                    delegated_target_label: str = target.label,
                    delegated_target_capability: str = agent_capability_summary(target),
                    delegating_agent_label: str = node.label,
                ) -> dict:
                    task = str(arguments.get("task") or "").strip()
                    if not task:
                        return {
                            "success": False,
                            "error_code": "invalid_delegation_task",
                            "error": "Delegation task cannot be blank",
                        }

                    if delegated_target_id in successful_delegation_targets:
                        await self._store.emit(
                            execution.id,
                            "delegation_skipped",
                            {
                                "target_node_id": str(delegated_target_id),
                                "target": delegated_target_label,
                                "reason": "already_completed_successfully",
                            },
                            invocation_id=invocation.id,
                        )
                        return {
                            "success": False,
                            "error_code": "duplicate_successful_delegation",
                            "error": (
                                "This Agent already completed a delegation successfully in "
                                "the current parent invocation. Reuse that result instead of "
                                "calling the same Agent again."
                            ),
                        }

                    remaining = remaining_seconds()
                    if remaining <= finalization_reserve_seconds:
                        await self._store.emit(
                            execution.id,
                            "delegation_skipped",
                            {
                                "target_node_id": str(delegated_target_id),
                                "target": delegated_target_label,
                                "reason": "network_deadline_near",
                                "remaining_seconds": round(remaining, 3),
                                "finalization_reserve_seconds": round(
                                    finalization_reserve_seconds,
                                    3,
                                ),
                            },
                            invocation_id=invocation.id,
                        )
                        return {
                            "success": False,
                            "error_code": "network_deadline_near",
                            "error": (
                                "No Network execution budget remains for another delegation. "
                                "Produce the final response now from completed results already "
                                "available in this Agent Run."
                            ),
                        }

                    context = arguments.get("context")
                    expected_output = str(arguments.get("expected_output") or "").strip()
                    fingerprint = _delegation_fingerprint(
                        target_node_id=delegated_target_id,
                        task=task,
                        context=context,
                        expected_output=expected_output,
                    )
                    if fingerprint in active_delegation_fingerprints:
                        await self._store.emit(
                            execution.id,
                            "delegation_skipped",
                            {
                                "target_node_id": str(delegated_target_id),
                                "target": delegated_target_label,
                                "reason": "duplicate_delegation",
                                "task_fingerprint": fingerprint,
                            },
                            invocation_id=invocation.id,
                        )
                        return {
                            "success": False,
                            "error_code": "duplicate_delegation",
                            "error": (
                                "An equivalent task is already being delegated to this "
                                "Agent in the current parent invocation."
                            ),
                        }

                    envelope: dict[str, object] = {
                        "delegated_by": delegating_agent_label,
                        "delegated_to": delegated_target_label,
                        "specialist_capability": delegated_target_capability,
                        "task": task,
                    }
                    if isinstance(context, dict) and context:
                        envelope["context"] = context
                    if expected_output:
                        envelope["expected_output"] = expected_output
                    delegated_message = (
                        "You are receiving a delegated task from another Agent in "
                        "the same Network Run. Complete it using your own "
                        "instructions and return the result to the delegating Agent.\n\n"
                        + json.dumps(envelope, ensure_ascii=False, indent=2)
                    )

                    active_delegation_fingerprints.add(fingerprint)
                    await self._store.emit(
                        execution.id,
                        "delegation_started",
                        {
                            "target_node_id": str(delegated_target_id),
                            "target": delegated_target_label,
                            "target_capability": delegated_target_capability,
                            "task_fingerprint": fingerprint,
                        },
                        invocation_id=invocation.id,
                    )
                    try:
                        child = await invoke_node(
                            delegated_target_id,
                            delegated_message,
                            depth + 1,
                            invocation.id,
                        )
                    except NetworkRuntimeFailure as failure:
                        await self._store.emit(
                            execution.id,
                            "delegation_failed",
                            {
                                "target_node_id": str(delegated_target_id),
                                "target": delegated_target_label,
                                "task_fingerprint": fingerprint,
                                **failure.public_payload(),
                            },
                            invocation_id=invocation.id,
                        )
                        return {
                            "success": False,
                            "error_code": failure.code,
                            "error": failure.safe_message,
                            "failure": failure.public_payload(),
                        }
                    finally:
                        active_delegation_fingerprints.discard(fingerprint)

                    successful_delegation_targets.add(delegated_target_id)
                    await self._store.emit(
                        execution.id,
                        "delegation_completed",
                        {
                            "target_node_id": str(delegated_target_id),
                            "target": delegated_target_label,
                            "result_type": (
                                "structured" if child.parsed_output is not None else "text"
                            ),
                            "task_fingerprint": fingerprint,
                        },
                        invocation_id=invocation.id,
                    )
                    return {
                        "success": True,
                        "result_type": (
                            "structured" if child.parsed_output is not None else "text"
                        ),
                        "result": (
                            child.parsed_output
                            if child.parsed_output is not None
                            else child.answer
                        ),
                    }

                tools.append(
                    InternalDelegationTool(
                        id=tool_id,
                        name=delegation_tool_name(target),
                        description=delegation_tool_description(target),
                        handler=delegate,
                    )
                )

            async def stream_agent_event(
                event_type: str,
                payload: dict[str, Any],
            ) -> None:
                if depth > 0 and event_type in {
                    "token",
                    "token_retract",
                    "assistant_message_delta",
                    "assistant_message_completed",
                }:
                    return
                await self._store.emit(
                    execution.id,
                    event_type,
                    payload,
                    invocation_id=invocation.id,
                )

            try:
                result = await self._invoker.invoke(
                    project_id=execution.project_id,
                    agent_id=node.agent_id,
                    release_id=release_uuid,
                    snapshot_override=snapshot_override,
                    message=message,
                    agent_session_id=invocation.agent_session_id,
                    execution_context=(
                        "playground" if runtime_environment == "draft" else runtime_environment
                    ),
                    internal_tools=tools,
                    network_context={
                        "network_id": str(execution.network_id),
                        "network_version_id": (
                            str(execution.network_version_id)
                            if execution.network_version_id
                            else None
                        ),
                        "network_session_id": str(execution.network_session_id),
                        "network_execution_id": str(execution.id),
                        "network_invocation_id": str(invocation.id),
                        "parent_invocation_id": (
                            str(parent_invocation_id) if parent_invocation_id else None
                        ),
                        "network_node_id": str(node_id),
                        "depth": depth,
                        "draft_revision": execution.draft_revision,
                        "tool_result_max_chars": definition.limits.tool_result_max_chars,
                    },
                    stream_handler=stream_agent_event,
                )
            except NetworkExecutionCancelled:
                # Cancellation is control flow, not an Agent failure. Keep the
                # in-flight invocation non-terminal here so the execution owner can
                # atomically convert all still-running invocations to CANCELLED.
                raise
            except NetworkBudgetExceeded as exc:
                await self._store.fail_invocation(invocation.id, str(exc))
                await self._store.emit(
                    execution.id,
                    "agent_invocation_failed",
                    {
                        "code": exc.code,
                        "stage": "network_budget",
                        "message": str(exc),
                        "retryable": False,
                        "cause_invocation_id": str(invocation.id),
                        "cause_node_id": str(node.id),
                        "cause_agent_id": str(node.agent_id),
                    },
                    invocation_id=invocation.id,
                )
                raise
            except Exception as exc:
                failure = classify_runtime_exception(exc).with_run_context(
                    invocation_id=invocation.id,
                    node_id=node.id,
                    agent_id=node.agent_id,
                )
                await self._store.fail_invocation(
                    invocation.id,
                    failure.internal_detail,
                    trace_id=failure.trace_id,
                    agent_session_id=failure.agent_session_id,
                    persist_context=persist_agent_context,
                )
                await self._store.emit(
                    execution.id,
                    "agent_invocation_failed",
                    failure.public_payload(),
                    invocation_id=invocation.id,
                )
                raise failure from exc

            await self._store.complete_invocation(
                invocation.id,
                result=result,
                persist_context=persist_agent_context,
            )
            if await self._store.is_cancel_requested(execution.id):
                raise NetworkExecutionCancelled("Network execution was cancelled")
            await self._store.emit(
                execution.id,
                "agent_invocation_completed",
                {
                    "trace_id": str(result.trace_id) if result.trace_id else None,
                    "agent_session_id": str(result.session_id) if result.session_id else None,
                    "provider": result.provider,
                    "model": result.model,
                    "usage": result.usage,
                    "tool_calls": result.tool_calls or [],
                    "sources": result.sources or [],
                    "parsed_output": result.parsed_output,
                    "output_parse_error": result.output_parse_error,
                    "output": result.answer,
                },
                invocation_id=invocation.id,
            )
            return result

        try:
            async with asyncio.timeout(timeout_seconds):
                return await invoke_node(
                    definition.root_node_id,
                    execution.input_message,
                    0,
                    None,
                )
        except TimeoutError as exc:
            raise NetworkBudgetExceeded(
                "Network execution timeout exceeded",
                code="network_timeout_exceeded",
            ) from exc
