from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from modules.agent.application.interfaces.agent_run_repository import AgentRunRepository
from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.database.run_models import AgentRunModel
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


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


class SQLAlchemyAgentRunRepository(AgentRunRepository):
    def __init__(self, uow: AgentUnitOfWork) -> None:
        self._uow = uow

    async def create(self, run: AgentRun) -> AgentRun:
        model = _to_model(run)
        self._uow.session.add(model)
        await self._uow.session.flush()
        await self._uow.session.refresh(model)
        return _to_entity(model)

    async def get_by_id(self, run_id: UUID) -> AgentRun | None:
        model = await self._uow.session.get(AgentRunModel, run_id)
        return _to_entity(model) if model is not None else None

    async def get_by_id_for_update(self, run_id: UUID) -> AgentRun | None:
        result = await self._uow.session.execute(
            select(AgentRunModel)
            .where(AgentRunModel.id == run_id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def save(self, run: AgentRun) -> AgentRun:
        model = await self._uow.session.get(AgentRunModel, run.id)
        if model is None:
            return await self.create(run)
        model.session_id = run.session_id
        model.agent_release_id = run.agent_release_id
        model.input_message_id = run.input_message_id
        model.output_message_id = run.output_message_id
        model.status = run.status.value
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
        await self._uow.session.refresh(model)
        return _to_entity(model)
