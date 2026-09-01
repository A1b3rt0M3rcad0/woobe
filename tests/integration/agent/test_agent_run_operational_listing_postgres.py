from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from modules.agent.domain.run import AgentRunStatus
from modules.agent.infra.database.agent_run_repository import SQLAlchemyAgentRunRepository
from modules.agent.infra.database.models import AgentModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_operational_agent_run_listing_does_not_depend_on_trace_projection() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    agent_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)

    try:
        async with session_factory() as session, session.begin():
            session.add(
                AgentModel(
                    id=agent_id,
                    project_id=project_id,
                    provider_credential_id=None,
                    fallback_credential_id=None,
                    name="Operational Run Agent",
                    description="",
                    type="assistant",
                    system_prompt="",
                    provider="openai",
                    model="test",
                    fallback_provider=None,
                    fallback_model=None,
                    temperature=0.2,
                    max_output_tokens=128,
                    session_mode="stateful",
                    status="active",
                    settings={},
                )
            )
            session.add(
                AgentRunModel(
                    id=run_id,
                    project_id=project_id,
                    agent_id=agent_id,
                    session_id=None,
                    agent_release_id=None,
                    input_message_id=None,
                    output_message_id=None,
                    trace_id=uuid4(),
                    environment="draft",
                    origin="runtime_api",
                    status="cancelled",
                    input_message="stop this answer",
                    execution_snapshot={},
                    usage=None,
                    result={
                        "answer": "partial",
                        "partial": True,
                        "cancelled": True,
                    },
                    failure_code=None,
                    failure_detail=None,
                    network_execution_id=None,
                    network_invocation_id=None,
                    parent_run_id=None,
                    rerun_of_run_id=None,
                    started_at=now,
                    completed_at=now,
                )
            )

        # No Trace/observability record is inserted. The operational Runs surface
        # must remain authoritative from AgentRun persistence alone while a Trace
        # projector is delayed, unavailable, or retrying.
        uow = AgentUnitOfWork(engine)
        async with uow:
            runs = await SQLAlchemyAgentRunRepository(uow).list_direct(
                project_id=project_id,
                agent_id=agent_id,
                environment="draft",
                limit=20,
            )

        assert len(runs) == 1
        assert runs[0].id == run_id
        assert runs[0].status == AgentRunStatus.CANCELLED
        assert runs[0].result == {
            "answer": "partial",
            "partial": True,
            "cancelled": True,
        }
    finally:
        await engine.dispose()
