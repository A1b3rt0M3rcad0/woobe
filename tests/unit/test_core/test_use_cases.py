import uuid6

import pytest

from modules.core.domain.errors import DuplicateSlugError, ProjectNotFoundError
from modules.core.application.dtos import CreateApiKeyInput, CreateProjectInput
from modules.core.application.use_cases import CreateApiKeyUseCase, CreateProjectUseCase
from modules.core.infra.security.api_key_issuer import SharedApiKeyIssuer
from tests.helpers import make_api_key, make_project


class TestCreateProjectUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        workspace_id = uuid6.uuid7()

        mock_repo = mocker.AsyncMock()
        mock_repo.get_by_workspace_and_slug.return_value = None
        mock_repo.save.return_value = make_project(
            workspace_id=workspace_id, name="MyProj", slug="my-proj"
        )

        mock_outbox = mocker.AsyncMock()

        uc = CreateProjectUseCase(project_repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(
            CreateProjectInput(workspace_id=workspace_id, name="MyProj", slug="my-proj")
        )

        assert result.name == "MyProj"
        assert result.slug == "my-proj"
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_duplicate_slug(self, mocker):
        workspace_id = uuid6.uuid7()

        mock_repo = mocker.AsyncMock()
        mock_repo.get_by_workspace_and_slug.return_value = make_project(
            slug="dup-slug"
        )

        uc = CreateProjectUseCase(project_repo=mock_repo, outbox=mocker.AsyncMock())
        with pytest.raises(DuplicateSlugError):
            await uc.execute(
                CreateProjectInput(
                    workspace_id=workspace_id, name="MyProj", slug="dup-slug"
                )
            )
        mock_repo.save.assert_not_called()


class TestCreateApiKeyUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        project_id = uuid6.uuid7()

        mock_project_repo = mocker.AsyncMock()
        mock_project_repo.get_by_id.return_value = make_project(
            workspace_id=uuid6.uuid7()
        )

        mock_api_key_repo = mocker.AsyncMock()
        mock_api_key_repo.save.return_value = make_api_key(project_id=project_id)

        mock_outbox = mocker.AsyncMock()

        uc = CreateApiKeyUseCase(
            project_repo=mock_project_repo,
            api_key_repo=mock_api_key_repo,
            outbox=mock_outbox,
            api_key_issuer=SharedApiKeyIssuer(),
        )
        result = await uc.execute(
            CreateApiKeyInput(
                project_id=project_id,
                name="MyKey",
                scopes=["reading"],
                created_by_user_id=uuid6.uuid7(),
            )
        )

        assert result.name == "TestKey"
        mock_api_key_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_project_not_found(self, mocker):
        mock_project_repo = mocker.AsyncMock()
        mock_project_repo.get_by_id.return_value = None

        uc = CreateApiKeyUseCase(
            project_repo=mock_project_repo,
            api_key_repo=mocker.AsyncMock(),
            outbox=mocker.AsyncMock(),
            api_key_issuer=SharedApiKeyIssuer(),
        )
        with pytest.raises(ProjectNotFoundError):
            await uc.execute(
                CreateApiKeyInput(
                    project_id=uuid6.uuid7(),
                    name="MyKey",
                    scopes=["reading"],
                    created_by_user_id=uuid6.uuid7(),
                )
            )
        mock_project_repo.get_by_id.assert_awaited_once()
