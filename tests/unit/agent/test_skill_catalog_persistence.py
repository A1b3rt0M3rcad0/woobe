from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import create_async_engine

from modules.agent.application.skill_packages import ImportSkillInput
from modules.agent.application.use_cases.skill_cases import SkillCatalog
from modules.agent.infra.database.skill_models import SkillModel, SkillVersionModel
from modules.agent.infra.database.skill_repository import SQLAlchemySkillRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.contracts.errors import ConflictError, NotFoundError
from shared.security.tenancy import TenantAuthorizer, _identifier_values


async def test_catalog_persists_versions_atomically_with_project_isolation():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.execute(text("ATTACH DATABASE ':memory:' AS agent"))
            with patch.object(
                SQLiteTypeCompiler,
                "visit_JSONB",
                lambda self, type_, **kw: "JSON",
                create=True,
            ):
                await connection.run_sync(
                    lambda conn: SkillModel.__table__.create(conn)
                )
                await connection.run_sync(
                    lambda conn: SkillVersionModel.__table__.create(conn)
                )
        project_id = uuid4()
        package = ImportSkillInput(
            version="1.0.0",
            skill_md="---\nname: test-procedure\ndescription: A reusable procedure\n---\nFollow the steps.",
        )
        async with AgentUnitOfWork(engine) as uow:
            catalog = SkillCatalog(SQLAlchemySkillRepository(uow))
            first = await catalog.create(project_id, package)
        async with AgentUnitOfWork(engine) as uow:
            catalog = SkillCatalog(SQLAlchemySkillRepository(uow))
            second = await catalog.add_version(
                project_id,
                first.skill_id,
                package.model_copy(
                    update={
                        "version": "2.0.0",
                        "skill_md": package.skill_md + "\nNew step.",
                    }
                ),
            )
            assert second.package_hash != first.package_hash
            assert (
                await catalog.get_version(project_id, first.id)
            ).package == first.package
            assert await catalog.list(uuid4(), query="", offset=0, limit=50) == []
            with pytest.raises(NotFoundError):
                await catalog.get_version(uuid4(), first.id)
            assert (
                len(
                    await catalog.versions(
                        project_id, first.skill_id, offset=0, limit=50
                    )
                )
                == 2
            )
        with pytest.raises(ConflictError):
            async with AgentUnitOfWork(engine) as uow:
                await SkillCatalog(SQLAlchemySkillRepository(uow)).add_version(
                    project_id, first.skill_id, package
                )
        async with AgentUnitOfWork(engine) as uow:
            assert (
                len(
                    await SQLAlchemySkillRepository(uow).list_versions(
                        project_id, first.skill_id
                    )
                )
                == 2
            )
    finally:
        await engine.dispose()


async def test_skill_version_authorization_resolves_owning_project_without_prompt_collision():
    project_id, version_id = uuid4(), uuid4()
    result = SimpleNamespace(scalar_one_or_none=lambda: project_id)
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    authorizer = TenantAuthorizer(session)
    assert (
        await authorizer._project_id_for_resource("skill_version_id", version_id)
        == project_id
    )
    sql = str(session.execute.call_args.args[0])
    assert "agent.skill_versions" in sql and "JOIN agent.skills" in sql
    assert "agent_prompts" not in sql
    identifiers = _identifier_values(
        {
            "runtime_config": {
                "skills": {
                    "bindings": [
                        {"skill_id": str(uuid4()), "skill_version_id": str(version_id)}
                    ]
                }
            }
        }
    )
    assert {key for key, value in identifiers} == {"skill_id", "skill_version_id"}


def test_skill_migration_has_single_head_and_reversible_postgres_ddl():
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "packages/woobe-core/alembic.ini"))
    assert ScriptDirectory.from_config(config).get_heads() == ["0064"]
    path = root / "packages/woobe-core/migrations/versions/0064_agent_skills.py"
    spec = spec_from_file_location("skill_migration", path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context):
        migration.upgrade()
        migration.downgrade()
    sql = output.getvalue()
    assert "CREATE TABLE agent.skills" in sql
    assert "CREATE TABLE agent.skill_versions" in sql
    assert "UNIQUE (skill_id, version)" in sql
    assert "DROP TABLE agent.skill_versions" in sql
    assert "REFERENCES core." not in sql
