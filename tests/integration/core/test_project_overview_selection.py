"""Read-side PostgreSQL fixtures, rolled back without creating accepted deployments."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from modules.core.infra.database.active_project_overview_reader import ActiveDocumentProjectOverviewReader
from modules.core.infra.database.project_overview_reader import _AGENT_ENVIRONMENT_CTE, SQLAlchemyProjectOverviewReader
from shared.infra.config import Settings


@pytest.mark.asyncio
async def test_overview_resolves_released_selection_and_same_release_in_both_environments():
    engine = create_async_engine(Settings().database_url, pool_pre_ping=True)
    project, resource, snapshot = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    try:
        async with AsyncSession(engine) as session:
            # Single transaction of read-side representations. No deployment,
            # acceptance receipt or customer resource is committed by this fixture.
            await session.execute(text("INSERT INTO core.projects(id,workspace_id,name,slug,status,data) VALUES(:id,:workspace,'Selection fixture',:slug,'active','{}'::jsonb)"),
                {'id': project, 'workspace': uuid4(), 'slug': 'selection-'+project.hex})
            await session.execute(text("INSERT INTO agent.agents(id,project_id,name,type,provider,model,session_mode,status,settings) VALUES(:id,:project,'Selected Agent','assistant','custom','test','stateless','active','{}'::jsonb)"), {'id': resource, 'project': project})
            await session.execute(text("INSERT INTO agent.agent_releases(id,project_id,agent_id,version,status,snapshot_kind,session_mode,created_at) VALUES(:id,:project,:agent,'1.2.0','released','release','stateless',:created)"),
                {'id': snapshot, 'project': project, 'agent': resource, 'created': now-timedelta(days=10)})
            for environment in ('staging', 'production'):
                await session.execute(text("INSERT INTO agent.asac_environment_selections(id,project_id,resource_id,environment,generation,snapshot_id,selection_authority,updated_at) VALUES(:id,:project,:agent,:environment,1,:snapshot,'asac',:now)"),
                    {'id': uuid4(), 'project': project, 'agent': resource, 'environment': environment, 'snapshot': snapshot, 'now': now})
            rows = (await session.execute(text(f'WITH {_AGENT_ENVIRONMENT_CTE} SELECT * FROM agent_environment'), {'project_id': project})).mappings().all()
            assert len(rows) == 1 and rows[0]['environment'] == 'production'
            reader = ActiveDocumentProjectOverviewReader(SimpleNamespace(session=session))
            releases = await reader._recent_agent_releases(session, {'project_id': project, 'start': now-timedelta(hours=1), 'end': now+timedelta(hours=1), 'environment': 'all', 'recent_limit': 10})
            assert {(row['id'], row['environment']) for row in releases} == {(snapshot, 'staging'), (snapshot, 'production')}
            assert all(row['promoted_at'] == now for row in releases)
            compatible = SQLAlchemyProjectOverviewReader(None)
            legacy_view = await compatible._recent_releases(session, {'project_id': project, 'environment': 'all', 'recent_limit': 10})
            assert {(row['id'], row['environment']) for row in legacy_view} == {(snapshot, 'staging'), (snapshot, 'production')}
            production = await reader._recent_agent_releases(session, {'project_id': project, 'start': now-timedelta(hours=1), 'end': now+timedelta(hours=1), 'environment': 'production', 'recent_limit': 10})
            assert len(production) == 1 and production[0]['id'] == snapshot
            foreign = (await session.execute(text(f'WITH {_AGENT_ENVIRONMENT_CTE} SELECT * FROM agent_environment'), {'project_id': uuid4()})).mappings().all()
            assert not foreign
            await session.rollback()
    finally:
        await engine.dispose()
