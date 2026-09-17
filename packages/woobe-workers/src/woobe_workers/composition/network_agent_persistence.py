from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from modules.agent.background_boundary import ContextEvidenceStore
from modules.agent.background_boundary import MessageModel, SessionModel
from modules.agent.background_boundary import AgentRunModel
from modules.network.background_boundary import AgentInvocationArtifact


def _message_id(artifact: AgentInvocationArtifact, role: str):
    return uuid5(
        NAMESPACE_URL,
        f"woobe:network-invocation:{artifact.invocation_id}:{role}",
    )


class ProjectRAIAgentInvocationArtifactMaterializer:
    """Persist Agent-owned artifacts for one Network child invocation.

    This adapter lives in the worker composition root because it coordinates two
    bounded contexts. It receives the Network finalizer's active SQLAlchemy
    session, so both sides are materialized atomically in the same transaction.
    """

    async def materialize(self, session, artifact: AgentInvocationArtifact) -> None:
        user_message_id = None
        assistant_message_id = None

        if artifact.session_id is None:
            raise ValueError("Network child Agent Run requires a Session")
        agent_session = await session.get(SessionModel, artifact.session_id)
        if agent_session is None:
            agent_session = SessionModel(
                id=artifact.session_id,
                project_id=artifact.project_id,
                agent_id=artifact.agent_id,
                runtime_environment=artifact.environment,
                opened_release_id=artifact.release_id,
                status="active",
                mode="chat",
                data={},
                last_message_at=artifact.completed_at,
            )
            session.add(agent_session)
        else:
            agent_session.last_message_at = artifact.completed_at

        user_message_id = _message_id(artifact, "user")
        if await session.get(MessageModel, user_message_id) is None:
            session.add(
                MessageModel(
                    id=user_message_id,
                    project_id=artifact.project_id,
                    agent_id=artifact.agent_id,
                    session_id=artifact.session_id,
                    role="user",
                    content=artifact.input_message,
                    data={
                        "network_execution_id": str(artifact.network_execution_id),
                        "network_invocation_id": str(artifact.invocation_id),
                    },
                )
            )

        if artifact.output_message:
            assistant_message_id = _message_id(artifact, "assistant")
            if await session.get(MessageModel, assistant_message_id) is None:
                session.add(
                    MessageModel(
                        id=assistant_message_id,
                        project_id=artifact.project_id,
                        agent_id=artifact.agent_id,
                        session_id=artifact.session_id,
                        role="assistant",
                        content=artifact.output_message,
                        input_tokens=(artifact.usage or {}).get("input_tokens"),
                        output_tokens=(artifact.usage or {}).get("output_tokens"),
                        cost_usd=(artifact.usage or {}).get("cost_usd"),
                        data={
                            "network_execution_id": str(artifact.network_execution_id),
                            "network_invocation_id": str(artifact.invocation_id),
                            "trace_id": (
                                str(artifact.trace_id)
                                if artifact.trace_id is not None
                                else None
                            ),
                            "provider": artifact.result.get("provider"),
                            "model": artifact.result.get("model"),
                            "latency_ms": (artifact.diagnostics or {}).get(
                                "agent_runtime_latency_ms"
                            ),
                            "tool_calls": artifact.tool_calls,
                            "sources": artifact.sources,
                            "parsed_output": artifact.parsed_output,
                            "output_parse_error": artifact.output_parse_error,
                            "cancelled": artifact.status == "cancelled",
                            "partial": artifact.status != "completed",
                        },
                    )
                )

        run = await session.get(AgentRunModel, artifact.invocation_id)
        if run is None:
            failure = artifact.failure
            run = AgentRunModel(
                id=artifact.invocation_id,
                project_id=artifact.project_id,
                agent_id=artifact.agent_id,
                session_id=artifact.session_id,
                agent_release_id=artifact.release_id,
                input_message_id=user_message_id,
                output_message_id=assistant_message_id,
                trace_id=artifact.trace_id
                or uuid5(
                    NAMESPACE_URL,
                    f"woobe:network-invocation-trace:{artifact.invocation_id}",
                ),
                environment=artifact.environment,
                origin="network_runtime",
                status=artifact.status,
                input_message=artifact.input_message,
                execution_snapshot=artifact.execution_snapshot,
                usage=artifact.usage,
                result=artifact.result,
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
                network_execution_id=artifact.network_execution_id,
                network_invocation_id=artifact.invocation_id,
                parent_run_id=artifact.parent_run_id,
                started_at=artifact.started_at,
                completed_at=artifact.completed_at,
            )
            session.add(run)

        await ContextEvidenceStore(session).persist_from_calls(
            agent_run_id=artifact.invocation_id,
            project_id=artifact.project_id,
            agent_id=artifact.agent_id,
            trace_id=run.trace_id,
            network_execution_id=artifact.network_execution_id,
            network_invocation_id=artifact.invocation_id,
            calls=artifact.llm_calls,
        )
