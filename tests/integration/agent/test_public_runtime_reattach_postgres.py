from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

import public_runtime_routes
from modules.agent.infra.database.models import AgentModel, SessionModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.execution.agent_run_reattach_service import (
    AgentRunReattachService,
)
from woobe_api.http.agent import run_routes as agent_run_routes
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.security.principal import ProjectApiPrincipal


@pytest.mark.asyncio
async def test_public_runtime_reattaches_cancelled_agent_from_durable_postgres(
    monkeypatch,
) -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    run_id = uuid4()
    trace_id = uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        async with session.begin():
            session.add(
                AgentModel(
                    id=agent_id,
                    project_id=project_id,
                    provider_credential_id=None,
                    fallback_credential_id=None,
                    name="public-runtime-reattach-agent",
                    description="",
                    type="assistant",
                    system_prompt="",
                    provider="openai",
                    model="test",
                    fallback_provider=None,
                    fallback_model=None,
                    temperature=0.2,
                    max_output_tokens=128,
                    session_mode="stateless",
                    status="active",
                    settings={},
                )
            )
        async with session.begin():
            session.add(
                SessionModel(
                    id=session_id,
                    project_id=project_id,
                    agent_id=agent_id,
                    runtime_environment="production",
                    opened_release_id=None,
                    chat_surface_id=None,
                    origin="runtime_api",
                    external_session_id=None,
                    tenant_id=None,
                    user_id=None,
                    status="active",
                    mode="chat",
                    data={"source": "public_runtime_reattach_test"},
                    last_message_at=now,
                )
            )
        async with session.begin():
            session.add(
                AgentRunModel(
                    id=run_id,
                    project_id=project_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    agent_release_id=None,
                    input_message_id=None,
                    output_message_id=None,
                    trace_id=trace_id,
                    environment="production",
                    origin="runtime_api",
                    status="cancelled",
                    input_message="cancel this run",
                    execution_snapshot={},
                    usage={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
                    result={
                        "answer": "persisted partial",
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

    transactions = AgentRuntimeTransactionRunner(
        lambda: AgentUnitOfWork(engine),
        lambda: AgentUnitOfWork(engine).mark_read_only(),
    )
    service = AgentRunReattachService(
        transactions=transactions,
        state_store=InMemoryExecutionStateStore(),
    )
    monkeypatch.setattr(
        agent_run_routes,
        "build_agent_run_reattach_operations",
        lambda: service,
    )

    principal = ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=project_id,
        key_prefix="rai_live_postgres_test",
        scopes=frozenset({"runtime:execute"}),
        kind="runtime",
        target_type="agent",
        target_id=agent_id,
        agent_id=agent_id,
        environment="production",
        interfaces=frozenset({"http", "stream"}),
        authenticated_at=now,
    )

    app = FastAPI()
    app.include_router(public_runtime_routes.router)

    @app.middleware("http")
    async def bind_runtime_principal(request: Request, call_next):
        request.state.principal = principal
        return await call_next(request)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            reattach = await client.get(f"/v1/runs/{run_id}/stream")
            cancel_retry = await client.post(f"/v1/runs/{run_id}/cancel")

        assert reattach.status_code == 200
        assert reattach.headers["content-type"].startswith("text/event-stream")
        assert reattach.headers["x-woobe-run-id"] == str(run_id)
        assert "event: run.state" in reattach.text
        assert '"protocol_version": 2' in reattach.text
        assert f'"run_id": "{run_id}"' in reattach.text
        assert f'"session_id": "{session_id}"' in reattach.text
        assert '"status": "cancelled"' in reattach.text
        assert '"output": "persisted partial"' in reattach.text
        assert '"realtime_available": false' in reattach.text

        assert cancel_retry.status_code == 202
        assert cancel_retry.json()["data"] == {
            "run_id": str(run_id),
            "status": "cancelled",
        }
    finally:
        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    delete(AgentRunModel).where(AgentRunModel.id == run_id)
                )
                await session.execute(
                    delete(SessionModel).where(SessionModel.id == session_id)
                )
                await session.execute(
                    delete(AgentModel).where(AgentModel.id == agent_id)
                )
        await engine.dispose()