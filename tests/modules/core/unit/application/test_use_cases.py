from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from modules.core.application.dtos.create_project_dtos import CreateProjectInput
from modules.core.application.dtos.create_api_key_dtos import CreateApiKeyInput
from modules.core.application.dtos.list_projects_dtos import ListProjectsInput
from modules.core.application.dtos.get_project_dtos import GetProjectInput
from modules.core.application.dtos.update_project_dtos import UpdateProjectInput
from modules.core.application.dtos.list_api_keys_dtos import ListApiKeysInput
from modules.core.application.use_cases.create_project_use_case import CreateProjectUseCase
from modules.core.application.use_cases.create_api_key_use_case import CreateApiKeyUseCase
from modules.core.application.use_cases.list_projects_use_case import ListProjectsUseCase
from modules.core.application.use_cases.get_project_use_case import GetProjectByIdUseCase
from modules.core.application.use_cases.update_project_use_case import UpdateProjectUseCase
from modules.core.application.use_cases.list_api_keys_use_case import ListApiKeysByProjectUseCase
from modules.core.domain.entities import ApiKey, Project

NOW = datetime.now(timezone.utc)


@pytest.fixture
def project():
    return Project(id=UUID("10000000-0000-0000-0000-000000000001"), name="test", slug="test", created_at=NOW, updated_at=NOW)


def _async_mock():
    return AsyncMock()


class TestCreateProjectUseCase:
    @pytest.mark.asyncio
    async def test_create_project(self, project):
        repo = AsyncMock()
        repo.get_by_organization_and_slug = AsyncMock(return_value=None)
        repo.save = AsyncMock(return_value=project)
        outbox = AsyncMock()
        outbox.write = AsyncMock()
        use_case = CreateProjectUseCase(repo, outbox)
        result = await use_case.execute(CreateProjectInput(organization_id=UUID(int=0), name="test", slug="test"))
        assert result.name == "test"
        assert result.slug == "test"
        outbox.write.assert_awaited_once()


class TestListProjectsUseCase:
    @pytest.mark.asyncio
    async def test_list_projects(self, project):
        repo = AsyncMock()
        repo.list_by_organization = AsyncMock(return_value=[project])
        use_case = ListProjectsUseCase(repo)
        result = await use_case.execute(ListProjectsInput(organization_id=UUID(int=0)))
        assert len(result) == 1


class TestGetProjectByIdUseCase:
    @pytest.mark.asyncio
    async def test_get_project(self, project):
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=project)
        use_case = GetProjectByIdUseCase(repo)
        result = await use_case.execute(GetProjectInput(project_id=UUID(int=0)))
        assert result.name == "test"


class TestUpdateProjectUseCase:
    @pytest.mark.asyncio
    async def test_update_project(self, project):
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=project)
        repo.save = AsyncMock(return_value=project)
        outbox = AsyncMock()
        outbox.write = AsyncMock()
        use_case = UpdateProjectUseCase(repo, outbox)
        result = await use_case.execute(UpdateProjectInput(project_id=UUID(int=0), name="updated"))
        assert result.name == "updated"


class TestCreateApiKeyUseCase:
    @pytest.mark.asyncio
    async def test_create_api_key(self, project):
        project_repo = AsyncMock()
        project_repo.get_by_id = AsyncMock(return_value=project)
        api_key_repo = AsyncMock()
        api_key_repo.save = AsyncMock(return_value=ApiKey(id=UUID(int=0), project_id=UUID(int=0), name="key", created_at=NOW))
        outbox = AsyncMock()
        outbox.write = AsyncMock()
        use_case = CreateApiKeyUseCase(project_repo, api_key_repo, outbox)
        result = await use_case.execute(CreateApiKeyInput(project_id=UUID(int=0), name="key", created_by_user_id=UUID(int=0)))
        assert result.name == "key"


class TestListApiKeysByProjectUseCase:
    @pytest.mark.asyncio
    async def test_list_api_keys(self):
        repo = AsyncMock()
        repo.list_by_project = AsyncMock(return_value=[ApiKey(id=UUID(int=0), name="key")])
        use_case = ListApiKeysByProjectUseCase(repo)
        result = await use_case.execute(ListApiKeysInput(project_id=UUID(int=0)))
        assert len(result) == 1
