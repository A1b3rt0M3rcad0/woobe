from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.infra.database import development_resource_reader as module
from shared.contracts.errors import NotFoundError


@pytest.mark.asyncio
@pytest.mark.parametrize("same_project", [True, False])
async def test_skill_version_scope_is_read_from_its_native_parent(monkeypatch, same_project):
    project_id, skill_id, version_id = uuid4(), uuid4(), uuid4()
    version = SimpleNamespace(id=version_id, skill_id=skill_id, updated_at=None, package_hash="immutable-hash", version="1.0.0")
    parent = SimpleNamespace(project_id=project_id if same_project else uuid4())
    session = SimpleNamespace(get=AsyncMock(side_effect=[version, parent]))
    monkeypatch.setattr(module, "authorize_export_read", AsyncMock())
    reader = module.DevelopmentResourceReader(lambda _: None)
    if same_project:
        result = await reader.inspect(session, project_id=project_id, principal="authorized", kind="Skill", resource_id=version_id)
        assert result["skill_id"] == str(skill_id)
        assert result["resource_id"] == str(version_id)
        assert result["revision"] == "immutable-hash"
    else:
        with pytest.raises(NotFoundError):
            await reader.inspect(session, project_id=project_id, principal="authorized", kind="Skill", resource_id=version_id)
    assert session.get.await_args_list[1].args == (module.SkillModel, skill_id)
