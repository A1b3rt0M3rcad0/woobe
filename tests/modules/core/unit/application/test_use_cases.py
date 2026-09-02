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
from modules.core.application.dtos.api_key_lifecycle_dtos import (
    RotateApiKeyInput,
    UpdateApiKeyCredentialInput,
)
from modules.core.application.use_cases.create_project_use_case import (
    CreateProjectUseCase,
)
from modules.core.application.use_cases.create_api_key_use_case import (
    CreateApiKeyUseCase,
)
from modules.core.application.use_cases.list_projects_use_case import (
    ListProjectsUseCase,
)
from modules.core.application.use_cases.get_project_use_case import (
    GetProjectByIdUseCase,
)
from modules.core.application.use_cases.update_project_use_case import (
    UpdateProjectUseCase,
)
from modules.core.application.use_cases.list_api_keys_use_case import (
    ListApiKeysByProjectUseCase,
)
from modules.core.application.use_cases.api_key_lifecycle_use_cases import (
    RotateApiKeyUseCase,
    UpdateApiKeyCredentialUseCase,
)
from modules.core.domain.entities import ApiKey, Project
from modules.core.domain.enums import ApiKeyKind, ApiKeyStatus, RuntimeEnvironment
from modules.core.infra.security.api_key_issuer import SharedApiKeyIssuer

NOW = datetime.now(timezone.utc)


@pytest.fixture
def project():
    return Project(
        id=UUID("10000000-0000-0000-0000-000000000001"),
        name="test",
        slug="test",
        created_at=NOW,
        updated_at=NOW,
    )


def _async_mock():
    return AsyncMock()


class TestCreateProjectUseCase:
    @pytest.mark.asyncio
    async def test_create_project(self, project):
        repo = AsyncMock()
        repo.get_by_workspace_and_slug = AsyncMock(return_value=None)
        repo.save = AsyncMock(return_value=project)
        outbox = AsyncMock()
        outbox.write = AsyncMock()
        use_case = CreateProjectUseCase(repo, outbox)
        result = await use_case.execute(
            CreateProjectInput(workspace_id=UUID(int=0), name="test", slug="test")
        )
        assert result.name == "test"
        assert result.slug == "test"
        outbox.write.assert_awaited_once()


class TestListProjectsUseCase:
    @pytest.mark.asyncio
    async def test_list_projects(self, project):
        repo = AsyncMock()
        repo.list_by_workspace = AsyncMock(return_value=[project])
        use_case = ListProjectsUseCase(repo)
        result = await use_case.execute(ListProjectsInput(workspace_id=UUID(int=0)))
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
        result = await use_case.execute(
            UpdateProjectInput(project_id=UUID(int=0), name="updated")
        )
        assert result.name == "updated"


class TestCreateApiKeyUseCase:
    @pytest.mark.asyncio
    async def test_create_api_key(self, project):
        project_repo = AsyncMock()
        project_repo.get_by_id = AsyncMock(return_value=project)
        api_key_repo = AsyncMock()
        api_key_repo.save = AsyncMock(
            return_value=ApiKey(
                id=UUID(int=0), project_id=UUID(int=0), name="key", created_at=NOW
            )
        )
        outbox = AsyncMock()
        outbox.write = AsyncMock()
        use_case = CreateApiKeyUseCase(
            project_repo, api_key_repo, outbox, SharedApiKeyIssuer()
        )
        result = await use_case.execute(
            CreateApiKeyInput(
                project_id=UUID(int=0),
                name="key",
                scopes=["traces:read"],
                created_by_user_id=UUID(int=0),
            )
        )
        assert result.name == "key"


class TestListApiKeysByProjectUseCase:
    @pytest.mark.asyncio
    async def test_list_api_keys(self):
        repo = AsyncMock()
        repo.list_by_project = AsyncMock(
            return_value=[ApiKey(id=UUID(int=0), name="key")]
        )
        use_case = ListApiKeysByProjectUseCase(repo, SharedApiKeyIssuer())
        result = await use_case.execute(ListApiKeysInput(project_id=UUID(int=0)))
        assert len(result) == 1
        assert result[0].credential_id == UUID(int=0)


class TestUpdateApiKeyCredentialUseCase:
    @pytest.mark.asyncio
    async def test_updates_metadata_for_the_logical_credential(self):
        project_id = UUID("10000000-0000-0000-0000-000000000001")
        credential_id = UUID("20000000-0000-0000-0000-000000000001")
        revision = ApiKey(
            id=UUID("30000000-0000-0000-0000-000000000001"),
            credential_id=credential_id,
            project_id=project_id,
            name="Old name",
        )
        saved = ApiKey(
            id=revision.id,
            credential_id=credential_id,
            project_id=project_id,
            name="Checkout backend",
            description="Production checkout integration",
        )
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=revision)
        repo.update_credential_metadata = AsyncMock(return_value=saved)
        outbox = AsyncMock()
        outbox.write = AsyncMock()
        use_case = UpdateApiKeyCredentialUseCase(repo, outbox)

        result = await use_case.execute(
            UpdateApiKeyCredentialInput(
                project_id=project_id,
                api_key_id=revision.id,
                updated_by_user_id=UUID(int=0),
                name=" Checkout backend ",
                description=" Production checkout integration ",
            )
        )

        assert result.credential_id == credential_id
        assert result.name == "Checkout backend"
        assert result.description == "Production checkout integration"
        repo.get_by_id.assert_awaited_once_with(revision.id)
        repo.update_credential_metadata.assert_awaited_once_with(
            credential_id,
            name="Checkout backend",
            description="Production checkout integration",
        )
        outbox.write.assert_awaited_once()


class TestRotateApiKeyCredential:
    @pytest.mark.asyncio
    async def test_rotation_keeps_logical_identity_and_metadata(self):
        project_id = UUID("10000000-0000-0000-0000-000000000001")
        credential_id = UUID("20000000-0000-0000-0000-000000000001")
        current = ApiKey(
            id=UUID("30000000-0000-0000-0000-000000000001"),
            credential_id=credential_id,
            project_id=project_id,
            name="Checkout backend",
            description="Production checkout integration",
            kind=ApiKeyKind.runtime,
            environment=RuntimeEnvironment.production,
            scopes=["runtime:execute"],
            status=ApiKeyStatus.active,
        )
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=current)
        repo.update = AsyncMock(return_value=current)

        async def save_replacement(replacement):
            replacement.created_at = NOW
            return replacement

        repo.save = AsyncMock(side_effect=save_replacement)
        outbox = AsyncMock()
        outbox.write = AsyncMock()
        use_case = RotateApiKeyUseCase(repo, outbox, SharedApiKeyIssuer())

        result = await use_case.execute(
            RotateApiKeyInput(
                project_id=project_id,
                api_key_id=current.id,
                rotated_by_user_id=UUID(int=0),
            )
        )

        assert result.credential_id == credential_id
        assert result.name == "Checkout backend"
        assert result.description == "Production checkout integration"
        assert result.rotated_from_id == current.id


class TestCreateProjectAccessAtomicity:
    @pytest.mark.asyncio
    async def test_checks_admin_and_grants_creator_in_same_use_case(self, project):
        actor_user_id = UUID("40000000-0000-0000-0000-000000000001")
        repo = AsyncMock()
        repo.get_by_workspace_and_slug = AsyncMock(return_value=None)
        repo.save = AsyncMock(return_value=project)
        outbox = AsyncMock()
        access_repo = AsyncMock()
        use_case = CreateProjectUseCase(repo, outbox, access_repo)

        await use_case.execute(
            CreateProjectInput(
                workspace_id=project.workspace_id,
                name=project.name,
                slug=project.slug,
                actor_user_id=actor_user_id,
            )
        )

        access_repo.require_workspace_admin.assert_awaited_once_with(
            actor_user_id,
            project.workspace_id,
        )
        access_repo.ensure_creator_access.assert_awaited_once_with(
            actor_user_id=actor_user_id,
            project_id=project.id,
        )
        outbox.write.assert_awaited_once()
