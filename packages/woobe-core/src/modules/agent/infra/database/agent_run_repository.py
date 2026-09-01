from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from modules.agent.application.interfaces.agent_run_repository import AgentRunRepository
from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.database.context_evidence_store import ContextEvidenceStore
from modules.agent.infra.database.models import MessageModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.contracts.errors import ConflictError


_TERMINAL_RUN_STATUSES = {
    AgentRunStatus.COMPLETED.value,
    AgentRunStatus.FAILED.value,
    AgentRunStatus.CANCELLED.value,
    AgentRunStatus.UNCERTAIN.value,
}


class AgentRunTerminalConflict(ConflictError):
    """Raised when a terminal writer loses the serialized Agent Run race."""

    def __init__(self, run_id: UUID, persisted_status: str, incoming_status: str) -> None:
        super().__init__(
            f"Agent Run {run_id} is already terminal as {persisted_status}; "
            f"cannot persist {incoming_status}"
        )
        self.run_id = run_id
        self.persisted_status = persisted_status
        self.incoming_status = incoming_status


def _to_model(run: AgentRun) -> AgentRunModel:
    return AgentRunModel(
        id=run.id,
        project_id=run.project_id,
        agent_id=run.agent_id,
        session_id=run.session_id,
        agent_release_id=run.agent_release_id,
        input_message_id=run.input_message_id,
        output_message_id=run.output_message_id,
        trace_id=run.trace_id,
        environment=run.environment,
        origin=run.origin,
        status=run.status.value,
        input_message=run.input_message,
        execution_snapshot=run.execution_snapshot,
        usage=run.usage,
        result=run.result,
        failure_code=run.failure_code,
        failure_detail=run.failure_detail,
        network_execution_id=run.network_execution_id,
        network_invocation_id=run.network_invocation_id,
        parent_run_id=run.parent_run_id,
        rerun_of_run_id=run.rerun_of_run_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _to_entity(model: AgentRunModel) -> AgentRun:
    return AgentRun(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        session_id=model.session_id,
        agent_release_id=model.agent_release_id,
        input_message_id=model.input_message_id,
        output_message_id=model.output_message_id,
        trace_id=model.trace_id,
        environment=model.environment,
        origin=model.origin,
        status=AgentRunStatus(model.status),
        input_message=model.input_message,
        execution_snapshot=dict(model.execution_snapshot or {}),
        usage=dict(model.usage) if model.usage is not None else None,
        result=dict(model.result) if model.result is not None else None,
        failure_code=model.failure_code,
        failure_detail=model.failure_detail,
        network_execution_id=model.network_execution_id,
        network_invocation_id=model.network_invocation_id,
        parent_run_id=model.parent_run_id,
        rerun_of_run_id=model.rerun_of_run_id,
        started_at=model.started_at,
        completed_at=model.completed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _embedded_invocations(run: AgentRun) -> list[dict]:
    result = run.result if isinstance(run.result, dict) else {}
    calls = result.get("llm_calls")
    if not isinstance(calls, list):
        return []
    invocations: list[dict] = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        snapshot = call.get("context_snapshot")
        if not isinstance(snapshot, dict):
            continue
        invocations.append(
            {
                "id": call.get("call_id"),
                "call_index": call.get("call_index"),
                "phase": call.get("phase"),
                "provider": call.get("provider"),
                "model": call.get("model"),
                "status": call.get("status"),
                "latency_ms": call.get("latency_ms"),
                "input_units": call.get("input_tokens"),
                "output_units": call.get("output_tokens"),
                "total_units": call.get("total_tokens"),
                "cost_usd": call.get("cost_usd"),
                "started_at": call.get("started_at"),
                "ended_at": call.get("ended_at"),
                "context_snapshot": snapshot,
                "persistence": "agent_run_embedded",
            }
        )
    return invocations


class SQLAlchemyAgentRunRepository(AgentRunRepository):
    def __init__(self, uow: AgentUnitOfWork) -> None:
        self._uow = uow

    async def _persist_context_evidence(self, run: AgentRun) -> None:
        if run.status == AgentRunStatus.RUNNING or not isinstance(run.result, dict):
            return
        calls = run.result.get("llm_calls")
        if not isinstance(calls, list) or not calls:
            return
        await ContextEvidenceStore(self._uow.session).persist_from_calls(
            agent_run_id=run.id,
            project_id=run.project_id,
            agent_id=run.agent_id,
            trace_id=run.trace_id,
            network_execution_id=run.network_execution_id,
            network_invocation_id=run.network_invocation_id,
            calls=calls,
        )

    async def create(self, run: AgentRun) -> AgentRun:
        model = _to_model(run)
        self._uow.session.add(model)
        await self._uow.session.flush()
        await self._persist_context_evidence(run)
        await self._uow.session.refresh(model)
        return _to_entity(model)

    async def get_by_id(self, run_id: UUID) -> AgentRun | None:
        model = await self._uow.session.get(AgentRunModel, run_id)
        return _to_entity(model) if model is not None else None

    async def get_by_trace_id(self, trace_id: UUID) -> AgentRun | None:
        result = await self._uow.session.execute(
            select(AgentRunModel)
            .where(AgentRunModel.trace_id == trace_id)
            .order_by(AgentRunModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def get_output_message_content(self, message_id: UUID) -> str | None:
        message = await self._uow.session.get(MessageModel, message_id)
        return str(message.content) if message is not None else None

    async def list_model_invocations(self, run_id: UUID) -> list[dict]:
        durable = await ContextEvidenceStore(self._uow.session).list_by_run(run_id)
        if durable:
            return durable
        run = await self.get_by_id(run_id)
        return _embedded_invocations(run) if run is not None else []

    async def list_direct(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID | None = None,
        environment: str | None = None,
        limit: int = 100,
    ) -> list[AgentRun]:
        statement = select(AgentRunModel).where(
            AgentRunModel.project_id == project_id,
            AgentRunModel.agent_id == agent_id,
            AgentRunModel.network_execution_id.is_(None),
        )
        if session_id is not None:
            statement = statement.where(AgentRunModel.session_id == session_id)
        if environment is not None:
            statement = statement.where(AgentRunModel.environment == environment)
        result = await self._uow.session.execute(
            statement
            .order_by(AgentRunModel.created_at.desc(), AgentRunModel.id.desc())
            .limit(max(1, min(int(limit), 200)))
        )
        return [_to_entity(model) for model in result.scalars().all()]

    async def get_active_direct_by_session(
        self,
        session_id: UUID,
    ) -> AgentRun | None:
        result = await self._uow.session.execute(
            select(AgentRunModel)
            .where(
                AgentRunModel.session_id == session_id,
                AgentRunModel.status == AgentRunStatus.RUNNING.value,
                AgentRunModel.network_execution_id.is_(None),
            )
            .order_by(AgentRunModel.created_at.desc(), AgentRunModel.id.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def get_by_id_for_update(self, run_id: UUID) -> AgentRun | None:
        result = await self._uow.session.execute(
            select(AgentRunModel)
            .where(AgentRunModel.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def save(self, run: AgentRun) -> AgentRun:
        result = await self._uow.session.execute(
            select(AgentRunModel)
            .where(AgentRunModel.id == run.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return await self.create(run)

        # Every terminal writer is serialized on the Run row. A persisted terminal
        # means this write lost ownership even when it proposes the same status:
        # accepting it would allow duplicate Assistant messages/outbox events staged
        # earlier in the same UoW. Raising rolls the entire UoW back atomically.
        incoming_status = run.status.value
        if model.status in _TERMINAL_RUN_STATUSES:
            raise AgentRunTerminalConflict(
                run.id,
                persisted_status=model.status,
                incoming_status=incoming_status,
            )

        model.session_id = run.session_id
        model.agent_release_id = run.agent_release_id
        model.input_message_id = run.input_message_id
        model.output_message_id = run.output_message_id
        model.status = incoming_status
        model.execution_snapshot = run.execution_snapshot
        model.usage = run.usage
        model.result = run.result
        model.failure_code = run.failure_code
        model.failure_detail = run.failure_detail
        model.network_execution_id = run.network_execution_id
        model.network_invocation_id = run.network_invocation_id
        model.parent_run_id = run.parent_run_id
        model.rerun_of_run_id = run.rerun_of_run_id
        model.started_at = run.started_at
        model.completed_at = run.completed_at
        await self._uow.session.flush()
        await self._persist_context_evidence(run)
        await self._uow.session.refresh(model)
        return _to_entity(model)