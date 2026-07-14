from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol
from uuid import UUID, uuid5

from modules.network.application.runtime_failures import classify_runtime_exception
from modules.network.domain.entities import NetworkDefinition, NetworkNode
from modules.network.domain.graph import delegation_tool_name
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkInvocationModel,
    NetworkVersionModel,
)


NETWORK_TOOL_NAMESPACE = UUID("bd84d8e4-0d63-4a8f-96ca-3fd22e42dfe0")


def agent_capability_summary(node: NetworkNode) -> str:
    capability = " ".join(node.capability_description.split())
    return capability or (
        f"This specialist performs the role represented by {node.label}."
    )


def delegation_tool_description(node: NetworkNode) -> str:
    capability = agent_capability_summary(node)
    return (
        f"Delegate a focused task to {node.label}. "
        f"Specialist capability: {capability} "
        "Use this specialist only when that capability is required. Send the "
        "precise task and only the context needed to complete it, then integrate "
        "the returned result into your response."
    )


class NetworkBudgetExceeded(RuntimeError):
    pass


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
                            "description": (
                                "The precise task the specialist must complete."
                            ),
                        },
                        "context": {
                            "type": "object",
                            "description": (
                                "Only the context required to complete the task."
                            ),
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
    ) -> AgentInvocationResult: ...


class NetworkExecutionStore(Protocol):
    async def is_cancel_requested(self, execution_id: UUID) -> bool: ...

    async def start_invocation(
        self,
        *,
        execution: NetworkExecutionModel,
        node_id: UUID,
        agent_id: UUID,
        depth: int,
        message: str,
        parent_invocation_id: UUID | None,
        persist_context: bool,
    ) -> NetworkInvocationModel: ...

    async def complete_invocation(
        self,
        invocation_id: UUID,
        *,
        result: AgentInvocationResult,
        persist_context: bool,
    ) -> None: ...

    async def fail_invocation(self, invocation_id: UUID, error: str) -> None: ...

    async def emit(
        self,
        execution_id: UUID,
        event_type: str,
        payload: dict,
        *,
        invocation_id: UUID | None = None,
    ) -> None: ...


class NetworkExecutor:
    def __init__(self, *, invoker: AgentInvoker, store: NetworkExecutionStore) -> None:
        self._invoker = invoker
        self._store = store

    async def execute(
        self,
        execution: NetworkExecutionModel,
        version: NetworkVersionModel | None,
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
            runtime_environment = (
                "production" if version.kind == "release" else "staging"
            )
        definition = NetworkDefinition.from_dict(definition_payload)
        nodes = {node.id: node for node in definition.nodes}
        outgoing: dict[UUID, list[UUID]] = {node_id: [] for node_id in nodes}
        for edge in definition.edges:
            outgoing[edge.source_node_id].append(edge.target_node_id)

        started = time.monotonic()
        invocation_count = 0
        count_lock = asyncio.Lock()

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
                raise NetworkBudgetExceeded("Network maximum depth exceeded")
            if time.monotonic() - started >= definition.limits.timeout_seconds:
                raise NetworkBudgetExceeded("Network execution timeout exceeded")
            async with count_lock:
                invocation_count += 1
                if invocation_count > definition.limits.max_invocations:
                    raise NetworkBudgetExceeded("Network invocation budget exceeded")

            node = nodes[node_id]
            binding = resolved_bindings.get(str(node_id)) or {}
            release_id = binding.get("release_id")
            snapshot_override = binding.get("snapshot_override")
            if runtime_environment == "draft" and not isinstance(
                snapshot_override, dict
            ):
                raise RuntimeError(f"Node {node_id} has no Agent Draft snapshot")
            if runtime_environment != "draft" and not release_id:
                raise RuntimeError(
                    f"Node {node_id} has no immutable Agent release binding"
                )

            invocation = await self._store.start_invocation(
                execution=execution,
                node_id=node.id,
                agent_id=node.agent_id,
                depth=depth,
                message=message,
                parent_invocation_id=parent_invocation_id,
                persist_context=definition.session_mode == "stateful",
            )
            await self._store.emit(
                execution.id,
                "agent_invocation_started",
                {
                    "label": node.label,
                    "invocation_count": invocation_count,
                    "provider": snapshot_override.get("provider")
                    if isinstance(snapshot_override, dict)
                    else None,
                    "model": snapshot_override.get("model")
                    if isinstance(snapshot_override, dict)
                    else None,
                    "source": "draft"
                    if runtime_environment == "draft"
                    else "release"
                    if runtime_environment == "production"
                    else "staging",
                    "version": (
                        f"r{execution.draft_revision}"
                        if runtime_environment == "draft"
                        else binding.get("release_version")
                    ),
                },
                invocation_id=invocation.id,
            )

            tools: list[InternalDelegationTool] = []
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
                            "error": "Delegation task cannot be blank",
                        }
                    context = arguments.get("context")
                    expected_output = str(
                        arguments.get("expected_output") or ""
                    ).strip()
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
                        "instructions and return the result to the delegating "
                        "Agent.\n\n"
                        + json.dumps(envelope, ensure_ascii=False, indent=2)
                    )
                    await self._store.emit(
                        execution.id,
                        "delegation_started",
                        {
                            "target_node_id": str(delegated_target_id),
                            "target": delegated_target_label,
                            "target_capability": delegated_target_capability,
                        },
                        invocation_id=invocation.id,
                    )
                    child = await invoke_node(
                        delegated_target_id,
                        delegated_message,
                        depth + 1,
                        invocation.id,
                    )
                    await self._store.emit(
                        execution.id,
                        "delegation_completed",
                        {
                            "target_node_id": str(delegated_target_id),
                            "target": delegated_target_label,
                        },
                        invocation_id=invocation.id,
                    )
                    return {"success": True, "output": {"answer": child.answer}}

                tools.append(
                    InternalDelegationTool(
                        id=tool_id,
                        name=delegation_tool_name(target),
                        description=delegation_tool_description(target),
                        handler=delegate,
                    )
                )

            try:
                result = await self._invoker.invoke(
                    project_id=execution.project_id,
                    agent_id=node.agent_id,
                    release_id=UUID(str(release_id)) if release_id else None,
                    snapshot_override=snapshot_override,
                    message=message,
                    agent_session_id=invocation.agent_session_id,
                    execution_context=(
                        "playground"
                        if runtime_environment == "draft"
                        else runtime_environment
                    ),
                    internal_tools=tools,
                    network_context={
                        "network_id": str(execution.network_id),
                        "network_version_id": str(execution.network_version_id)
                        if execution.network_version_id
                        else None,
                        "network_session_id": str(execution.network_session_id),
                        "network_execution_id": str(execution.id),
                        "network_invocation_id": str(invocation.id),
                        "parent_invocation_id": str(parent_invocation_id)
                        if parent_invocation_id
                        else None,
                        "network_node_id": str(node_id),
                        "depth": depth,
                        "draft_revision": getattr(execution, "draft_revision", None),
                    },
                )
            except NetworkExecutionCancelled as exc:
                await self._store.fail_invocation(invocation.id, str(exc))
                await self._store.emit(
                    execution.id,
                    "agent_invocation_failed",
                    {
                        "code": "execution_cancelled",
                        "stage": "network_control",
                        "message": "The Network Run was cancelled.",
                        "retryable": False,
                        "cause_invocation_id": str(invocation.id),
                        "cause_node_id": str(node.id),
                        "cause_agent_id": str(node.agent_id),
                    },
                    invocation_id=invocation.id,
                )
                raise
            except NetworkBudgetExceeded as exc:
                await self._store.fail_invocation(invocation.id, str(exc))
                await self._store.emit(
                    execution.id,
                    "agent_invocation_failed",
                    {
                        "code": "budget_exceeded",
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
                await self._store.fail_invocation(invocation.id, str(exc))
                failure = classify_runtime_exception(exc).with_run_context(
                    invocation_id=invocation.id,
                    node_id=node.id,
                    agent_id=node.agent_id,
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
                persist_context=definition.session_mode == "stateful",
            )
            if await self._store.is_cancel_requested(execution.id):
                raise NetworkExecutionCancelled("Network execution was cancelled")
            await self._store.emit(
                execution.id,
                "agent_invocation_completed",
                {
                    "trace_id": str(result.trace_id) if result.trace_id else None,
                    "agent_session_id": str(result.session_id)
                    if result.session_id
                    else None,
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
            async with asyncio.timeout(definition.limits.timeout_seconds):
                return await invoke_node(
                    definition.root_node_id,
                    execution.input_message,
                    0,
                    None,
                )
        except TimeoutError as exc:
            raise NetworkBudgetExceeded("Network execution timeout exceeded") from exc
