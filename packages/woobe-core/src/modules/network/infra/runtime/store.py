from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.network.application.runtime import AgentInvocationResult
from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionModel,
    NetworkInvocationModel,
)
from modules.network.infra.database.repositories import NetworkRuntimeRepository


def should_persist_agent_context(
    *,
    network_persists_context: bool,
    agent_session_mode: str,
) -> bool:
    return network_persists_context and agent_session_mode == "stateful"


class SQLNetworkExecutionStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def is_cancel_requested(self, execution_id: UUID) -> bool:
        async with self._session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            return execution is None or execution.status in {
                "cancel_requested",
                "cancelled",
            }

    @staticmethod
    async def _resolve_agent_session_mode(
        session: AsyncSession,
        *,
        project_id: UUID,
        agent_id: UUID,
        release_id: UUID | None,
        snapshot_override: dict[str, Any] | None,
        binding_session_mode: str | None = None,
    ) -> str:
        # Runtime execution must consume the session mode frozen into the Network
        # binding. Looking up an Agent Release here would make a Network Run depend
        # on mutable cross-context infrastructure after its execution snapshot was
        # accepted.
        del session, project_id, agent_id
        if binding_session_mode is not None:
            if binding_session_mode in {"stateful", "stateless"}:
                return binding_session_mode
            raise RuntimeError("Pinned Agent binding has no valid session_mode")

        if release_id is not None:
            raise RuntimeError("Pinned Agent binding has no frozen session_mode")

        if isinstance(snapshot_override, dict):
            session_mode = snapshot_override.get("session_mode")
            if session_mode in {"stateful", "stateless"}:
                return str(session_mode)
            raise RuntimeError("Agent Draft snapshot has no valid session_mode")

        raise RuntimeError("Agent runtime binding has no release or Draft snapshot")

    async def resolve_agent_session_mode(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        release_id: UUID | None,
        snapshot_override: dict[str, Any] | None,
        binding_session_mode: str | None = None,
    ) -> str:
        async with self._session_factory() as session:
            return await self._resolve_agent_session_mode(
                session,
                project_id=project_id,
                agent_id=agent_id,
                release_id=release_id,
                snapshot_override=snapshot_override,
                binding_session_mode=binding_session_mode,
            )

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
    ) -> NetworkInvocationModel:
        async with self._session_factory() as session, session.begin():
            persisted_execution = await session.get(NetworkExecutionModel, execution.id)
            if persisted_execution is None:
                raise RuntimeError("Network execution was not found")

            repository = NetworkRuntimeRepository(session)
            context = (
                await repository.get_or_create_agent_context(
                    network_session_id=persisted_execution.network_session_id,
                    node_id=node_id,
                    agent_id=agent_id,
                )
                if persist_context
                else None
            )
            return await repository.create_invocation(
                execution=persisted_execution,
                node_id=node_id,
                agent_id=agent_id,
                depth=depth,
                input_message=message,
                parent_invocation_id=parent_invocation_id,
                agent_session_id=context.agent_session_id if context else None,
            )

    async def complete_invocation(
        self,
        invocation_id: UUID,
        *,
        result: AgentInvocationResult,
        persist_context: bool,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            invocation = await session.get(NetworkInvocationModel, invocation_id)
            if invocation is None:
                return
            invocation.status = "completed"
            invocation.output_message = result.answer
            setattr(invocation, "parsed_output", result.parsed_output)
            setattr(invocation, "output_parse_error", result.output_parse_error)
            invocation.trace_id = result.trace_id
            if result.session_id:
                invocation.agent_session_id = result.session_id
            if result.session_id and persist_context:
                from sqlalchemy import select

                context = await session.scalar(
                    select(NetworkAgentContextModel).where(
                        NetworkAgentContextModel.network_session_id
                        == invocation.network_session_id,
                        NetworkAgentContextModel.network_node_id == invocation.node_id,
                    )
                )
                if context is not None:
                    context.agent_session_id = result.session_id

    async def persist_execution_output(
        self,
        execution_id: UUID,
        result: AgentInvocationResult,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            execution = await session.get(
                NetworkExecutionModel,
                execution_id,
                with_for_update=True,
            )
            if execution is None:
                return
            setattr(execution, "parsed_output", result.parsed_output)
            setattr(execution, "output_parse_error", result.output_parse_error)
            await NetworkRuntimeRepository(session).append_event(
                execution,
                "network_result",
                {
                    "answer": result.answer,
                    "result": result.parsed_output
                    if result.parsed_output is not None
                    else result.answer,
                    "parsed_output": result.parsed_output,
                    "output_parse_error": result.output_parse_error,
                    "result_type": "structured"
                    if result.parsed_output is not None
                    else "text",
                    "trace_id": str(result.trace_id) if result.trace_id else None,
                },
            )

    async def fail_invocation(
        self,
        invocation_id: UUID,
        error: str,
        *,
        trace_id: UUID | None = None,
        agent_session_id: UUID | None = None,
        persist_context: bool = False,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            invocation = await session.get(NetworkInvocationModel, invocation_id)
            if invocation is not None:
                invocation.status = "failed"
                invocation.error = error[:4000]
                if trace_id is not None:
                    invocation.trace_id = trace_id
                if agent_session_id is not None:
                    invocation.agent_session_id = agent_session_id
                if agent_session_id is not None and persist_context:
                    from sqlalchemy import select

                    context = await session.scalar(
                        select(NetworkAgentContextModel).where(
                            NetworkAgentContextModel.network_session_id
                            == invocation.network_session_id,
                            NetworkAgentContextModel.network_node_id
                            == invocation.node_id,
                        )
                    )
                    if context is not None:
                        context.agent_session_id = agent_session_id

    async def emit(
        self,
        execution_id: UUID,
        event_type: str,
        payload: dict,
        *,
        invocation_id: UUID | None = None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            execution = await session.get(
                NetworkExecutionModel,
                execution_id,
                with_for_update=True,
            )
            if execution is None:
                return
            invocation = (
                await session.get(NetworkInvocationModel, invocation_id)
                if invocation_id
                else None
            )
            await NetworkRuntimeRepository(session).append_event(
                execution,
                event_type,
                payload,
                invocation=invocation,
            )
