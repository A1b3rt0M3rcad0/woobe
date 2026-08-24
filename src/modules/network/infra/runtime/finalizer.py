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
    NetworkExecutionModel,
    NetworkInvocationModel,
)
from modules.network.infra.database.repositories import NetworkRuntimeRepository


def _uuid(value: Any) -> UUID | None:
    if value in {None, ""}:
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


def _message_id(invocation_id: UUID, role: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"woobe:network-invocation:{invocation_id}:{role}")


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

            for item in invocation_states:
                invocation_id = _uuid(item.get("id"))
                agent_id = _uuid(item.get("agent_id"))
                node_id = _uuid(item.get("node_id"))
                if invocation_id is None or agent_id is None or node_id is None:
                    continue
                parent_id = _uuid(item.get("parent_invocation_id"))
                session_id = _uuid(item.get("agent_session_id"))
                invocation_trace_id = _uuid(item.get("trace_id"))
                status = str(item.get("status") or "failed")
                binding = bindings.get(str(node_id))
                binding = binding if isinstance(binding, dict) else {}
                release_id = _uuid(binding.get("release_id"))
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
                result_payload = {
                    "answer": item.get("output_message"),
                    "provider": item.get("provider"),
                    "model": item.get("model"),
                    "usage": usage,
                    "tool_calls": item.get("tool_calls") or [],
                    "sources": item.get("sources") or [],
                    "parsed_output": item.get("parsed_output"),
                    "output_parse_error": item.get("output_parse_error"),
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
                            last_message_at=now,
                        )
                        session.add(agent_session)
                    else:
                        agent_session.last_message_at = now

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
                                        "tool_calls": item.get("tool_calls") or [],
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
                        status=("completed" if status == "completed" else "failed"),
                        input_message=str(item.get("input_message") or ""),
                        execution_snapshot=execution_snapshot,
                        usage=usage,
                        result=result_payload,
                        failure_code=(
                            None if status == "completed" else "network_agent_failure"
                        ),
                        failure_detail=item.get("error"),
                        network_execution_id=execution.id,
                        network_invocation_id=invocation_id,
                        parent_run_id=parent_id,
                        started_at=now,
                        completed_at=now,
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
                        error=item.get("error"),
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

            repository = NetworkRuntimeRepository(session)
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
