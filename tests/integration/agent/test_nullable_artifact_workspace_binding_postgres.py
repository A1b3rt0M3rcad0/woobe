from uuid import uuid4

import pytest
from sqlalchemy import delete, text

from modules.agent.infra.database.models import AgentModel, SessionModel
from modules.core.infra.database.models import ProjectModel
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


@pytest.mark.asyncio
async def test_none_artifact_workspace_binding_persists_as_sql_null_under_migration_check():
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    project_id, agent_id, session_id = uuid4(), uuid4(), uuid4()

    try:
        async with session_factory() as db, db.begin():
            db.add(ProjectModel(
                id=project_id,
                workspace_id=uuid4(),
                name="Nullable artifact binding test",
                slug=f"nullable-artifact-binding-{project_id}",
                status="active",
                data={},
            ))
            await db.flush()
            db.add(AgentModel(
                id=agent_id,
                project_id=project_id,
                provider_credential_id=None,
                fallback_credential_id=None,
                name="Nullable artifact binding test agent",
                description="",
                type="assistant",
                system_prompt="",
                provider="openai",
                model="test-model",
                fallback_provider=None,
                fallback_model=None,
                temperature=0.0,
                max_output_tokens=32,
                session_mode="stateless",
                status="active",
                settings={},
            ))
            await db.flush()
            db.add(SessionModel(
                id=session_id,
                project_id=project_id,
                agent_id=agent_id,
                runtime_environment="draft",
                opened_release_id=None,
                chat_surface_id=None,
                origin="runtime_api",
                external_session_id=None,
                tenant_id=None,
                user_id=None,
                status="active",
                mode="chat",
                data={},
                external_context_snapshot=None,
                artifact_workspace_binding=None,
                last_message_at=None,
            ))

        async with session_factory() as db:
            persisted_as_sql_null = await db.scalar(text(
                "SELECT artifact_workspace_binding IS NULL "
                "FROM agent.sessions WHERE id = :session_id"
            ), {"session_id": session_id})
            migration_check_is_valid = await db.scalar(text(
                "SELECT convalidated FROM pg_constraint "
                "WHERE conname = 'ck_agent_session_artifact_workspace_binding' "
                "AND conrelid = 'agent.sessions'::regclass"
            ))

        assert persisted_as_sql_null is True
        assert migration_check_is_valid is True
    finally:
        async with session_factory() as db, db.begin():
            await db.execute(delete(SessionModel).where(SessionModel.id == session_id))
            await db.execute(delete(AgentModel).where(AgentModel.id == agent_id))
            await db.execute(delete(ProjectModel).where(ProjectModel.id == project_id))
        await engine.dispose()
