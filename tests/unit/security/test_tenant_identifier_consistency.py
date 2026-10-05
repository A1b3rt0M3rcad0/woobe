from __future__ import annotations

from uuid import uuid4

import pytest

from shared.infra.errors import ConflictError
from shared.security.tenancy import TenantAuthorizer


def test_nested_multi_agent_references_are_not_scalar_context_conflicts() -> None:
    project_id = uuid4()
    first_agent_id = uuid4()
    second_agent_id = uuid4()
    body = {
        "project_id": project_id,
        "definition": {
            "nodes": [
                {"agent_id": first_agent_id},
                {"agent_id": second_agent_id},
            ]
        },
    }

    all_identifiers = TenantAuthorizer._identifiers({}, {}, body)
    consistency_identifiers = TenantAuthorizer._consistency_identifiers({}, {}, body)

    assert ("agent_id", first_agent_id) in all_identifiers
    assert ("agent_id", second_agent_id) in all_identifiers
    assert consistency_identifiers == [("project_id", project_id)]
    TenantAuthorizer._require_consistent_identifiers(consistency_identifiers)


def test_top_level_resource_identifier_conflicts_are_still_rejected() -> None:
    first_agent_id = uuid4()
    second_agent_id = uuid4()
    identifiers = TenantAuthorizer._consistency_identifiers(
        {"agent_id": first_agent_id},
        {},
        {"agent_id": second_agent_id},
    )

    with pytest.raises(ConflictError, match="Conflicting agent_id values in request"):
        TenantAuthorizer._require_consistent_identifiers(identifiers)


def test_nested_project_identifiers_remain_visible_to_project_authorization() -> None:
    outer_project_id = uuid4()
    nested_project_id = uuid4()
    body = {
        "project_id": outer_project_id,
        "definition": {
            "metadata": {"project_id": nested_project_id},
        },
    }

    all_identifiers = TenantAuthorizer._identifiers({}, {}, body)
    consistency_identifiers = TenantAuthorizer._consistency_identifiers({}, {}, body)

    assert ("project_id", outer_project_id) in all_identifiers
    assert ("project_id", nested_project_id) in all_identifiers
    assert consistency_identifiers == [("project_id", outer_project_id)]


@pytest.mark.asyncio
async def test_project_key_ownership_resolves_direct_and_indirect_uuid_bindings():
    from sqlalchemy import event, text
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from shared.contracts.errors import NotFoundError
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    @event.listens_for(engine.sync_engine, "connect")
    def attach(connection, _):
        connection.execute("ATTACH DATABASE ':memory:' AS agent")
        connection.execute("ATTACH DATABASE ':memory:' AS network")
    project, agent, network, version = uuid4(), uuid4(), uuid4(), uuid4()
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE agent.agents (id TEXT, project_id TEXT)"))
            await conn.execute(text("CREATE TABLE network.networks (id TEXT, project_id TEXT)"))
            await conn.execute(text("CREATE TABLE network.network_versions (id TEXT, network_id TEXT)"))
            await conn.execute(text("INSERT INTO agent.agents VALUES (:id, :project)"), {"id": agent.hex, "project": project.hex})
            await conn.execute(text("INSERT INTO network.networks VALUES (:id, :project)"), {"id": network.hex, "project": project.hex})
            await conn.execute(text("INSERT INTO network.network_versions VALUES (:id, :network)"), {"id": version.hex, "network": network.hex})
        async with async_sessionmaker(engine)() as session:
            authorizer = TenantAuthorizer(session)
            for key, resource in [("agent_id", agent), ("source_version_id", version)]:
                await authorizer.authorize_api_key(project_id=project,
                    path_params={key: resource}, query_params={}, body={})
                with pytest.raises(NotFoundError):
                    await authorizer.authorize_api_key(project_id=uuid4(),
                        path_params={key: resource}, query_params={}, body={})
    finally:
        await engine.dispose()
