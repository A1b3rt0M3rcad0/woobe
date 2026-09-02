from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.context_evidence_store import ContextEvidenceStore
from modules.agent.infra.database.models import MessageModel, SessionModel
from modules.agent.infra.database.run_models import AgentRunModel


def _message_id(invocation_id: UUID, role: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"woobe:network-invocation:{invocation_id}:{role}")


class AgentNetworkRunMaterializer:
    """Materialize one Network Agent invocation into Agent durable history.

    The caller owns the SQL transaction. This adapter deliberately receives an
    existing AsyncSession so Agent Run history and Network finalization commit
    atomically without exposing Agent ORM models to the Network bounded context.
    """

    async def materialize(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        agent_id: UUID,
        invocation_id: UUID,
        session_id: UUID | None,
        release_id: UUID | None,
        trace_id: UUID | None,
        parent_run_id: UUID | None,
        environment: str,
        input_message: str,
        output_message: str | None,
        status: str,
        execution_snapshot: dict[str, Any],
        provider: str | None,
        model: str | None,
        usage: dict[str, Any] | None,
        diagnostics: dict[str, Any] | None,
        llm_calls: list[dict[str, Any]],
        tool_calls: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        parsed_output: dict[str, Any] | None,
        output_parse_error: str | None,
        failure: dict[str, Any] | None,
        network_execution_id: UUID,
        started_at: datetime,
        completed_at: datetime,
    ) -> None:
        user_message_id: UUID | None = None
        assistant_message_id: UUID | None = None

        if session_id is not None:
            agent_session = await session.get(SessionModel, session_id)
            if agent_session is None:
                agent_session = SessionModel(
                    id=session_id,
                    project_id=project_id,
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
                        project_id=project_id,
                        agent_id=agent_id,
                        session_id=session_id,
                        role="user",
                        content=input_message,
                        data={
                            "network_execution_id": str(network_execution_id),
                            "network_invocation_id": str(invocation_id),
                        },
                    )
                )

            if output_message:
                assistant_message_id = _message_id(invocation_id, "assistant")
                if await session.get(MessageModel, assistant_message_id) is None:
                    session.add(
                        MessageModel(
                            id=assistant_message_id,
                            project_id=project_id,
                            agent_id=agent_id,
                            session_id=session_id,
                            role="assistant",
                            content=output_message,
                            input_tokens=(usage or {}).get("input_tokens"),
                            output_tokens=(usage or {}).get("output_tokens"),
                            cost_usd=(usage or {}).get("cost_usd"),
                            data={
                                "network_execution_id": str(network_execution_id),
                                "network_invocation_id": str(invocation_id),
                                "trace_id": str(trace_id) if trace_id else None,
                                "provider": provider,
                                "model": model,
                                "latency_ms": (diagnostics or {}).get(
                                    "agent_runtime_latency_ms"
                                ),
                                "tool_calls": tool_calls,
                                "sources": sources,
                                "parsed_output": parsed_output,
                                "output_parse_error": output_parse_error,
                                "cancelled": status == "cancelled",
                                "partial": status != "completed",
                            },
                        )
                    )

        run = await session.get(AgentRunModel, invocation_id)
        if run is None:
            run_trace_id = trace_id or uuid5(
                NAMESPACE_URL,
                f"woobe:network-invocation-trace:{invocation_id}",
            )
            result_payload = {
                "answer": output_message,
                "provider": provider,
                "model": model,
                "usage": usage,
                "diagnostics": diagnostics,
                "llm_calls": llm_calls,
                "tool_calls": tool_calls,
                "sources": sources,
                "parsed_output": parsed_output,
                "output_parse_error": output_parse_error,
                "fallback_used": bool((diagnostics or {}).get("fallback_used")),
                "cost_status": (diagnostics or {}).get("cost_status"),
                "cost_usd": (usage or {}).get("cost_usd"),
                "cancelled": status == "cancelled",
                "partial": status != "completed" and bool(output_message),
                "failure": failure,
            }
            run = AgentRunModel(
                id=invocation_id,
                project_id=project_id,
                agent_id=agent_id,
                session_id=session_id,
                agent_release_id=release_id,
                input_message_id=user_message_id,
                output_message_id=assistant_message_id,
                trace_id=run_trace_id,
                environment=environment,
                origin="network_runtime",
                status=status,
                input_message=input_message,
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
                network_execution_id=network_execution_id,
                network_invocation_id=invocation_id,
                parent_run_id=parent_run_id,
                started_at=started_at,
                completed_at=completed_at,
            )
            session.add(run)

        await ContextEvidenceStore(session).persist_from_calls(
            agent_run_id=invocation_id,
            project_id=project_id,
            agent_id=agent_id,
            trace_id=run.trace_id,
            network_execution_id=network_execution_id,
            network_invocation_id=invocation_id,
            calls=llm_calls,
        )


__all__ = ["AgentNetworkRunMaterializer"]
