from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from shared.contracts.errors import AuthorizationError, NotFoundError
from shared.security.tenancy import TenantAuthorizer


@pytest_asyncio.fixture
async def runtime_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    @event.listens_for(engine.sync_engine, "connect")
    def attach(connection, _):
        connection.execute("ATTACH DATABASE ':memory:' AS agent")
        connection.execute("ATTACH DATABASE ':memory:' AS network")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE agent.agent_runs (id TEXT PRIMARY KEY, agent_id TEXT, environment TEXT, trace_id TEXT)"))
        await conn.execute(text("CREATE TABLE network.network_sessions (id TEXT PRIMARY KEY, network_id TEXT, environment TEXT)"))
        await conn.execute(text("CREATE TABLE network.network_executions (id TEXT PRIMARY KEY, network_id TEXT, network_session_id TEXT)"))
    yield async_sessionmaker(engine)
    await engine.dispose()


@pytest.mark.asyncio
async def test_stored_run_conditions_override_supplied_environment(runtime_db):
    run, agent = uuid4(), uuid4()
    async with runtime_db() as session:
        await session.execute(text("INSERT INTO agent.agent_runs VALUES (:id, :agent, 'production', :trace)"),
                              {"id": run.hex, "agent": agent.hex, "trace": uuid4().hex})
        authorizer = TenantAuthorizer(session)
        conditions = {"target_ids": [str(agent)], "environments": ["staging"]}
        path = await authorizer._condition_path_context(conditions, "run:read", {"run_id": run})
        with pytest.raises(AuthorizationError):
            authorizer._require_conditions(conditions, permission="run:read", path_context=path,
                                          context={"environment": "staging"})
        authorizer._require_conditions({"target_ids": [str(agent)], "environments": ["production"]},
                                       permission="run:read", path_context=path)
        with pytest.raises(NotFoundError):
            await authorizer._condition_path_context(conditions, "run:read", {"run_id": uuid4()})


@pytest.mark.asyncio
async def test_run_trace_lookup_preserves_target_restrictions(runtime_db):
    run, agent, trace = uuid4(), uuid4(), uuid4()
    async with runtime_db() as session:
        await session.execute(text("INSERT INTO agent.agent_runs VALUES (:id, :agent, 'production', :trace)"),
                              {"id": run.hex, "agent": agent.hex, "trace": trace.hex})
        authorizer = TenantAuthorizer(session)
        conditions = {"target_ids": [str(agent)]}
        path = await authorizer._condition_path_context(conditions, "run:read", {"run_trace_id": trace})
        authorizer._require_conditions(conditions, permission="run:read", path_context=path)
        with pytest.raises(AuthorizationError):
            authorizer._require_conditions({"target_ids": [str(uuid4())]}, permission="run:read", path_context=path)


@pytest.mark.asyncio
async def test_network_execution_uses_session_environment(runtime_db):
    execution, network, session_id = uuid4(), uuid4(), uuid4()
    async with runtime_db() as session:
        await session.execute(text("INSERT INTO network.network_sessions VALUES (:id, :network, 'production')"),
                              {"id": session_id.hex, "network": network.hex})
        await session.execute(text("INSERT INTO network.network_executions VALUES (:id, :network, :session)"),
                              {"id": execution.hex, "network": network.hex, "session": session_id.hex})
        authorizer = TenantAuthorizer(session)
        conditions = {"target_ids": [str(network)], "target_types": ["network"], "environments": ["production"]}
        path = await authorizer._condition_path_context(conditions, "run:read", {"execution_id": execution})
        authorizer._require_conditions(conditions, permission="run:read", path_context=path)
        with pytest.raises(AuthorizationError):
            authorizer._require_conditions({"environments": ["staging"]}, permission="run:read", path_context=path)
