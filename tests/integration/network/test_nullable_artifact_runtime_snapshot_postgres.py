from uuid import uuid4

import pytest
from sqlalchemy import delete, text

from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkModel,
    NetworkSessionModel,
)
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_nullable_network_artifact_snapshots_persist_as_sql_null_under_checks():
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id, network_id, session_id, execution_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )

    try:
        async with session_factory() as db, db.begin():
            db.add(
                NetworkModel(
                    id=network_id,
                    project_id=project_id,
                    name=f"nullable-artifact-{network_id}",
                    description="",
                    draft_definition={},
                    draft_revision=1,
                    staging_version_id=None,
                    production_version_id=None,
                )
            )
            await db.flush()
            db.add(
                NetworkSessionModel(
                    id=session_id,
                    network_id=network_id,
                    network_version_id=None,
                    project_id=project_id,
                    origin="runtime_api",
                    environment="draft",
                    title="Nullable artifact binding test",
                    status="active",
                    artifact_workspace_binding=None,
                )
            )
            await db.flush()
            db.add(
                NetworkExecutionModel(
                    id=execution_id,
                    network_id=network_id,
                    network_version_id=None,
                    network_session_id=session_id,
                    project_id=project_id,
                    input_message="test",
                    draft_revision=1,
                    definition_snapshot={},
                    resolved_bindings_snapshot={},
                    artifact_workspace_binding=None,
                    runtime_principal_snapshot=None,
                    status="queued",
                )
            )

        async with session_factory() as db:
            persisted_as_sql_null = await db.execute(
                text(
                    "SELECT "
                    "(SELECT artifact_workspace_binding IS NULL "
                    " FROM network.network_sessions WHERE id = :session_id), "
                    "(SELECT artifact_workspace_binding IS NULL "
                    " FROM network.network_executions WHERE id = :execution_id), "
                    "(SELECT runtime_principal_snapshot IS NULL "
                    " FROM network.network_executions WHERE id = :execution_id)"
                ),
                {"session_id": session_id, "execution_id": execution_id},
            )
            checks_are_valid = await db.execute(
                text(
                    "SELECT conname, convalidated FROM pg_constraint "
                    "WHERE conname IN ("
                    "'ck_network_session_artifact_workspace_binding', "
                    "'ck_network_execution_artifact_runtime_snapshot')"
                )
            )

        assert persisted_as_sql_null.one() == (True, True, True)
        assert dict(checks_are_valid.all()) == {
            "ck_network_session_artifact_workspace_binding": True,
            "ck_network_execution_artifact_runtime_snapshot": True,
        }
    finally:
        async with session_factory() as db, db.begin():
            await db.execute(
                delete(NetworkExecutionModel).where(
                    NetworkExecutionModel.id == execution_id
                )
            )
            await db.execute(
                delete(NetworkSessionModel).where(NetworkSessionModel.id == session_id)
            )
            await db.execute(delete(NetworkModel).where(NetworkModel.id == network_id))
        await engine.dispose()
