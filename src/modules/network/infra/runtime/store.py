from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.network.application.runtime import AgentInvocationResult
from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionModel,
    NetworkInvocationModel,
)
from modules.network.infra.database.repositories import NetworkRuntimeRepository


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
            repository = NetworkRuntimeRepository(session)
            context = (
                await repository.get_or_create_agent_context(
                    network_session_id=execution.network_session_id,
                    node_id=node_id,
                    agent_id=agent_id,
                )
                if persist_context
                else None
            )
            invocation = await repository.create_invocation(
                execution=execution,
                node_id=node_id,
                agent_id=agent_id,
                depth=depth,
                input_message=message,
                parent_invocation_id=parent_invocation_id,
                agent_session_id=context.agent_session_id if context else None,
            )
            return invocation

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
