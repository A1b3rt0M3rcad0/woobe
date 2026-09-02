from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from modules.network.application.dtos.runtime import (
    AgentInvocationResult,
    NetworkExecutionSnapshot,
)
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkInvocationModel,
)
from modules.network.infra.database.repositories import NetworkRuntimeRepository
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


NetworkUnitOfWorkFactory = Callable[[], NetworkUnitOfWork]


def should_persist_agent_context(
    *,
    network_persists_context: bool,
    agent_session_mode: str,
) -> bool:
    return network_persists_context and agent_session_mode == "stateful"


class SQLNetworkExecutionStore:
    """Persistence adapter using one short NetworkUnitOfWork per operation."""

    def __init__(self, uow_factory: NetworkUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def is_cancel_requested(self, execution_id: UUID) -> bool:
        uow = self._uow_factory().mark_read_only()
        async with uow:
            execution = await uow.session.get(NetworkExecutionModel, execution_id)
            return execution is None or execution.status in {
                "cancel_requested",
                "cancelled",
            }

    @staticmethod
    def _resolve_agent_session_mode(
        *,
        release_id: UUID | None,
        snapshot_override: dict[str, Any] | None,
        binding_session_mode: str | None = None,
    ) -> str:
        if binding_session_mode is not None:
            if binding_session_mode in {"stateful", "stateless"}:
                return binding_session_mode
            raise RuntimeError("Pinned Agent binding has no valid session_mode")

        if isinstance(snapshot_override, dict):
            session_mode = snapshot_override.get("session_mode")
            if session_mode in {"stateful", "stateless"}:
                return str(session_mode)
            raise RuntimeError("Agent Draft snapshot has no valid session_mode")

        if release_id is not None:
            raise RuntimeError(
                "Pinned Agent release is missing the frozen session_mode binding"
            )
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
        del project_id, agent_id
        return self._resolve_agent_session_mode(
            release_id=release_id,
            snapshot_override=snapshot_override,
            binding_session_mode=binding_session_mode,
        )

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
    ) -> NetworkInvocationModel:
        async with self._uow_factory() as uow:
            persisted_execution = await uow.session.get(
                NetworkExecutionModel,
                execution.id,
            )
            if persisted_execution is None:
                raise RuntimeError("Network execution was not found")

            repository = NetworkRuntimeRepository(uow.session)
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
        async with self._uow_factory() as uow:
            invocation = await uow.session.get(NetworkInvocationModel, invocation_id)
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
                context = await NetworkRuntimeRepository(
                    uow.session
                ).get_or_create_agent_context(
                    network_session_id=invocation.network_session_id,
                    node_id=invocation.node_id,
                    agent_id=invocation.agent_id,
                )
                context.agent_session_id = result.session_id

    async def persist_execution_output(
        self,
        execution_id: UUID,
        result: AgentInvocationResult,
    ) -> None:
        async with self._uow_factory() as uow:
            execution = await uow.session.get(
                NetworkExecutionModel,
                execution_id,
                with_for_update=True,
            )
            if execution is None:
                return
            setattr(execution, "parsed_output", result.parsed_output)
            setattr(execution, "output_parse_error", result.output_parse_error)
            await NetworkRuntimeRepository(uow.session).append_event(
                execution,
                "network_result",
                {
                    "answer": result.answer,
                    "result": (
                        result.parsed_output
                        if result.parsed_output is not None
                        else result.answer
                    ),
                    "parsed_output": result.parsed_output,
                    "output_parse_error": result.output_parse_error,
                    "result_type": (
                        "structured" if result.parsed_output is not None else "text"
                    ),
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
        async with self._uow_factory() as uow:
            invocation = await uow.session.get(NetworkInvocationModel, invocation_id)
            if invocation is None:
                return
            invocation.status = "failed"
            invocation.error = error[:4000]
            if trace_id is not None:
                invocation.trace_id = trace_id
            if agent_session_id is not None:
                invocation.agent_session_id = agent_session_id
            if agent_session_id is not None and persist_context:
                context = await NetworkRuntimeRepository(
                    uow.session
                ).get_or_create_agent_context(
                    network_session_id=invocation.network_session_id,
                    node_id=invocation.node_id,
                    agent_id=invocation.agent_id,
                )
                context.agent_session_id = agent_session_id

    async def emit(
        self,
        execution_id: UUID,
        event_type: str,
        payload: dict,
        *,
        invocation_id: UUID | None = None,
    ) -> None:
        async with self._uow_factory() as uow:
            execution = await uow.session.get(
                NetworkExecutionModel,
                execution_id,
                with_for_update=True,
            )
            if execution is None:
                return
            invocation = (
                await uow.session.get(NetworkInvocationModel, invocation_id)
                if invocation_id
                else None
            )
            await NetworkRuntimeRepository(uow.session).append_event(
                execution,
                event_type,
                payload,
                invocation=invocation,
            )
