from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.models import MessageModel, SessionModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.network.application.runtime import NetworkVersionSnapshot
from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkInvocationModel,
)
from modules.network.infra.database.repositories import NetworkRuntimeRepository


def _uuid(value: Any) -> UUID | None:
    if value in {None, ""}:
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


def _datetime(value: Any, *, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return fallback


def _message_id(invocation_id: UUID, role: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"woobe:network-invocation:{invocation_id}:{role}")


def _invocation_failure(
    item: dict[str, Any],
    *,
    terminal_failure_code: str | None,
    terminal_failure_detail: str | None,
) -> dict[str, Any]:
    raw = item.get("failure")
    if isinstance(raw, dict):
        failure = dict(raw)
    else:
        detail = (
            str(item.get("error") or "").strip()
            or str(terminal_failure_detail or "").strip()
            or "Agent invocation failed"
        )
        code = terminal_failure_code or "network_agent_failure"
        failure = {
            "code": code,
            "stage": "network_runtime",
            "message": (
                str(terminal_failure_detail or "").strip()
                or detail
            ),
            "retryable": False,
            "internal_detail": detail,
        }

    failure.setdefault("code", terminal_failure_code or "network_agent_failure")
    failure.setdefault("stage", "network_runtime")
    failure.setdefault(
        "message",
        str(terminal_failure_detail or "").strip()
        or str(item.get("error") or "").strip()
        or "Agent invocation failed",
    )
    failure.setdefault("retryable", False)
    failure.setdefault(
        "internal_detail",
        str(item.get("error") or "").strip()
        or str(failure.get("message") or "").strip()
        or "Agent invocation failed",
    )
    return failure


class NetworkRuntimeFinalizer:
    """Materialize one complete Network execution in one PostgreSQL transaction."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _environment(version: NetworkVersionSnapshot | None) -> str:
        if version is None:
            return "draft"
        return "production" if version.kind == "release" else "staging"

    @staticmethod
    def _bindings(
        version: NetworkVersionSnapshot | None,
        execution: NetworkExecutionModel,
    ) -> dict[str, Any]:
        value = (
            version.resolved_bindings
            if version is not None
            else execution.resolved_bindings_snapshot
        )
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _binding_source(environment: str, binding: dict[str, Any]) -> str:
        source = binding.get("binding_source")
        if source in {"draft", "staging", "release"}:
            return str(source)
        if environment == "draft":
            return "draft"
        return "release" if environment == "production" else "staging"

    async def finalize(
        self,
        *,
        execution_id: UUID,
        version: NetworkVersionSnapshot | None,
        invocation_states: list[dict[str, Any]],
        terminal_status: str,
        output: str | None,
        trace_id: UUID | None,
        failure_code: str | None = None,
        failure_detail: str | None = None,
        uncertain: bool = False,
        streamed_output: bool = False,
    ) -> bool:
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session, session.begin():
            execution = await session.scalar(
                select(NetworkExecutionModel)
                .where(NetworkExecutionModel.id == execution_id)
                .with_for_update()
            )
            if execution is None:
                return False
            if execution.status in {"completed", "failed", "cancelled", "uncertain"}:
                return True

            environment = self._environment(version)
            bindings = self._bindings(version, execution)
            repository = NetworkRuntimeRepository(session)
            durable_invocation_events: list[
                tuple[datetime, int, str, dict[str, Any], dict[str, Any]]
            ] = []

            for item in invocation_states:
                invocation_id = _uuid(item.get("id"))
                agent_id = _uuid(item.get("agent_id"))
                node_id = _uuid(item.get("node_id"))
                if invocation_id is None or agent_id is None or node_id is None:
                    continue
                parent_id = _uuid(item.get("parent_invocation_id"))
                session_id = _uuid(item.get("agent_session_id"))
                invocation_trace_id = _uuid(item.get("trace_id"))
                hot_status = str(item.get("status") or "failed")
                status = "completed" if hot_status == "completed" else "failed"
                failure = (
                    None
                    if status == "completed"
                    else _invocation_failure(
                        item,
                        terminal_failure_code=failure_code,
                        terminal_failure_detail=failure_detail,
                    )
                )
                binding = bindings.get(str(node_id))
                binding = binding if isinstance(binding, dict) else {}
                release_id = _uuid(binding.get("release_id"))
                started_at = _datetime(item.get("started_at"), fallback=now)
                completed_at = _datetime(item.get("completed_at"), fallback=now)
                if completed_at < started_at:
                    completed_at = started_at
                execution_snapshot = {
                    "network_execution_id": str(execution.id),
                    "network_version_id": (
                        str(execution.network_version_id)
                        if execution.network_version_id
                        else None
                    ),
                    "network_node_id": str(node_id),
                    "network_binding": binding,
                }
                usage = item.get("usage") if isinstance(item.get("usage"), dict) else None
                diagnostics = (
                    item.get("diagnostics")
                    if isinstance(item.get("diagnostics"), dict)
                    else None
                )
                llm_calls = (
                    item.get("llm_calls")
                    if isinstance(item.get("llm_calls"), list)
                    else []
                )
                result_payload = {
                    "answer": item.get("output_message"),
                    "provider": item.get("provider"),
                    "model": item.get("model"),
                    "usage": usage,
                    "diagnostics": diagnostics,
                    "llm_calls": llm_calls,
                    "tool_calls": item.get("tool_calls") or [],
                    "sources": item.get("sources") or [],
                    "parsed_output": item.get("parsed_output"),
                    "output_parse_error": item.get("output_parse_error"),
                    "fallback_used": bool((diagnostics or {}).get("fallback_used")),
                    "cost_status": (diagnostics or {}).get("cost_status"),
                    "cost_usd": (usage or {}).get("cost_usd"),
                    "failure": failure,
                }

                if session_id is not None:
                    agent_session = await session.get(SessionModel, session_id)
                    if agent_session is None:
                        agent_session = SessionModel(
                            id=session_id,
                            project_id=execution.project_id,
                            agent_id=agent_id,
                            runtime_environment=environment,
                            opened_release_id=release_id,
                            status="active",
                            mode="chat",
                            data={},
                            last_message_at=completed_at,
                        )
                        session.add(agent_session)
                    else:
                        agent_session.last_message_at = completed_at

                    user_message_id = _message_id(invocation_id, "user")
                    if await session.get(MessageModel, user_message_id) is None:
                        session.add(
                            MessageModel(
                                id=user_message_id,
                                project_id=execution.project_id,
                                agent_id=agent_id,
                                session_id=session_id,
                                role="user",
                                content=str(item.get("input_message") or ""),
                                data={
                                    "network_execution_id": str(execution.id),
                                    "network_invocation_id": str(invocation_id),
                                },
                            )
                        )
                    if item.get("output_message") is not None:
                        assistant_message_id = _message_id(invocation_id, "assistant")
                        if await session.get(MessageModel, assistant_message_id) is None:
                            session.add(
                                MessageModel(
                                    id=assistant_message_id,
                                    project_id=execution.project_id,
                                    agent_id=agent_id,
                                    session_id=session_id,
                                    role="assistant",
                                    content=str(item.get("output_message") or ""),
                                    input_tokens=(usage or {}).get("input_tokens"),
                                    output_tokens=(usage or {}).get("output_tokens"),
                                    cost_usd=(usage or {}).get("cost_usd"),
                                    data={
                                        "network_execution_id": str(execution.id),
                                        "network_invocation_id": str(invocation_id),
                                        "trace_id": (
                                            str(invocation_trace_id)
                                            if invocation_trace_id
                                            else None
                                        ),
                                        "provider": item.get("provider"),
                                        "model": item.get("model"),
                                        "latency_ms": (diagnostics or {}).get(
                                            "agent_runtime_latency_ms"
                                        ),
                                        "tool_calls": item.get("tool_calls") or [],
                                        "sources": item.get("sources") or [],
                                        "parsed_output": item.get("parsed_output"),
                                        "output_parse_error": item.get("output_parse_error"),
                                    },
                                )
                            )

                run = await session.get(AgentRunModel, invocation_id)
                if run is None:
                    run = AgentRunModel(
                        id=invocation_id,
                        project_id=execution.project_id,
                        agent_id=agent_id,
                        session_id=session_id,
                        agent_release_id=release_id,
                        trace_id=invocation_trace_id
                        or uuid5(
                            NAMESPACE_URL,
                            f"woobe:network-invocation-trace:{invocation_id}",
                        ),
                        environment=environment,
                        origin="network_runtime",
                        status=status,
                        input_message=str(item.get("input_message") or ""),
                        execution_snapshot=execution_snapshot,
                        usage=usage,
                        result=result_payload,
                        failure_code=(
                            None
                            if failure is None
                            else str(failure.get("code") or "network_agent_failure")
                        ),
                        failure_detail=(
                            None
                            if failure is None
                            else str(
                                failure.get("internal_detail")
                                or failure.get("message")
                                or "Agent invocation failed"
                            )
                        ),
                        network_execution_id=execution.id,
                        network_invocation_id=invocation_id,
                        parent_run_id=parent_id,
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                    session.add(run)

                invocation = await session.get(NetworkInvocationModel, invocation_id)
                if invocation is None:
                    invocation = NetworkInvocationModel(
                        id=invocation_id,
                        network_execution_id=execution.id,
                        network_session_id=execution.network_session_id,
                        parent_invocation_id=parent_id,
                        node_id=node_id,
                        agent_id=agent_id,
                        agent_session_id=session_id,
                        trace_id=invocation_trace_id,
                        depth=int(item.get("depth") or 0),
                        status=status,
                        input_message=str(item.get("input_message") or ""),
                        output_message=item.get("output_message"),
                        error=(
                            None
                            if failure is None
                            else str(
                                failure.get("internal_detail")
                                or failure.get("message")
                                or "Agent invocation failed"
                            )
                        ),
                    )
                    if hasattr(invocation, "parsed_output"):
                        setattr(invocation, "parsed_output", item.get("parsed_output"))
                    if hasattr(invocation, "output_parse_error"):
                        setattr(
                            invocation,
                            "output_parse_error",
                            item.get("output_parse_error"),
                        )
                    session.add(invocation)

                source = self._binding_source(environment, binding)
                version_label = (
                    f"r{execution.draft_revision}"
                    if environment == "draft"
                    else binding.get("release_version")
                )
                durable_invocation_events.append(
                    (
                        started_at,
                        0,
                        "agent_invocation_started",
                        {
                            "provider": item.get("provider"),
                            "model": item.get("model"),
                            "session_mode": binding.get("session_mode"),
                            "context_state": (
                                "created" if item.get("persist_context") else "stateless"
                            ),
                            "source": source,
                            "version": version_label,
                            "started_at": started_at.isoformat(),
                        },
                        {
                            "id": invocation_id,
                            "parent_id": parent_id,
                            "node_id": node_id,
                            "agent_id": agent_id,
                            "depth": int(item.get("depth") or 0),
                        },
                    )
                )
                terminal_event_type = (
                    "agent_invocation_completed"
                    if status == "completed"
                    else "agent_invocation_failed"
                )
                terminal_payload = (
                    {
                        "trace_id": (
                            str(invocation_trace_id) if invocation_trace_id else None
                        ),
                        "agent_session_id": str(session_id) if session_id else None,
                        "provider": item.get("provider"),
                        "model": item.get("model"),
                        "usage": usage,
                        "diagnostics": diagnostics,
                        "tool_calls": item.get("tool_calls") or [],
                        "sources": item.get("sources") or [],
                        "parsed_output": item.get("parsed_output"),
                        "output_parse_error": item.get("output_parse_error"),
                        "output": item.get("output_message"),
                        "started_at": started_at.isoformat(),
                        "completed_at": completed_at.isoformat(),
                    }
                    if failure is None
                    else {
                        "code": str(failure.get("code") or "network_agent_failure"),
                        "stage": str(failure.get("stage") or "network_runtime"),
                        "message": str(
                            failure.get("message") or "Agent invocation failed"
                        ),
                        "retryable": failure.get("retryable") is True,
                        "phase": failure.get("phase"),
                        "call_index": failure.get("call_index"),
                        "upstream_status": failure.get("upstream_status"),
                        "upstream_error_code": failure.get("upstream_error_code"),
                        "partial_result_available": (
                            failure.get("partial_result_available") is True
                        ),
                        "trace_id": (
                            failure.get("trace_id")
                            or (
                                str(invocation_trace_id)
                                if invocation_trace_id
                                else None
                            )
                        ),
                        "cause_invocation_id": (
                            failure.get("cause_invocation_id")
                            or str(invocation_id)
                        ),
                        "cause_node_id": (
                            failure.get("cause_node_id") or str(node_id)
                        ),
                        "cause_agent_id": (
                            failure.get("cause_agent_id") or str(agent_id)
                        ),
                        "started_at": started_at.isoformat(),
                        "completed_at": completed_at.isoformat(),
                    }
                )
                durable_invocation_events.append(
                    (
                        completed_at,
                        1,
                        terminal_event_type,
                        terminal_payload,
                        {
                            "id": invocation_id,
                            "parent_id": parent_id,
                            "node_id": node_id,
                            "agent_id": agent_id,
                            "depth": int(item.get("depth") or 0),
                        },
                    )
                )

                if item.get("persist_context") and session_id is not None:
                    context = await session.scalar(
                        select(NetworkAgentContextModel).where(
                            NetworkAgentContextModel.network_session_id
                            == execution.network_session_id,
                            NetworkAgentContextModel.network_node_id == node_id,
                        )
                    )
                    if context is None:
                        session.add(
                            NetworkAgentContextModel(
                                network_session_id=execution.network_session_id,
                                network_node_id=node_id,
                                agent_id=agent_id,
                                agent_session_id=session_id,
                            )
                        )
                    else:
                        context.agent_id = agent_id
                        context.agent_session_id = session_id

            for occurred_at, _, event_type, payload, identity in sorted(
                durable_invocation_events,
                key=lambda value: (value[0], value[1], str(value[4]["id"])),
            ):
                execution.last_event_sequence += 1
                session.add(
                    NetworkExecutionEventModel(
                        network_execution_id=execution.id,
                        network_session_id=execution.network_session_id,
                        sequence=execution.last_event_sequence,
                        event_type=event_type,
                        invocation_id=identity["id"],
                        parent_invocation_id=identity["parent_id"],
                        node_id=identity["node_id"],
                        agent_id=identity["agent_id"],
                        depth=identity["depth"],
                        payload=payload,
                        created_at=occurred_at,
                    )
                )

            if terminal_status == "completed":
                await repository.mark_completed(
                    execution,
                    output=output or "",
                    root_trace_id=trace_id,
                )
                if output and not streamed_output:
                    await repository.append_event(
                        execution,
                        "token",
                        {
                            "content": output,
                            "channel": "final",
                            "visibility": "assistant",
                        },
                    )
                await repository.append_event(
                    execution,
                    "execution_completed",
                    {"trace_id": str(trace_id) if trace_id else None},
                )
            elif terminal_status == "cancelled":
                execution.status = "cancelled"
                execution.completed_at = now
                execution.lease_owner = None
                execution.lease_expires_at = None
                await repository.append_event(execution, "execution_cancelled", {})
            else:
                await repository.mark_failed(
                    execution,
                    code=failure_code or "runtime_error",
                    detail=failure_detail or "Network execution failed",
                    root_trace_id=trace_id,
                    uncertain=uncertain,
                )
                await repository.append_event(
                    execution,
                    "execution_failed",
                    {
                        "code": failure_code or "runtime_error",
                        "uncertain": uncertain,
                        "trace_id": str(trace_id) if trace_id else None,
                    },
                )
            return True