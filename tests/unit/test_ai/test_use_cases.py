import uuid6

import pytest

from modules.ai.domain.errors import CredentialNotFoundError
from modules.ai.service.dtos import CreateAgentInput, CreateProviderCredentialInput
from modules.ai.service.use_cases import (
    CreateAgentUseCase,
    CreateProviderCredentialUseCase,
)
from tests.helpers import make_agent, make_provider_credential


class TestCreateProviderCredentialUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        project_id = uuid6.uuid7()

        mock_repo = mocker.AsyncMock()
        mock_repo.save.return_value = make_provider_credential(
            project_id=project_id
        )

        mock_outbox = mocker.AsyncMock()

        uc = CreateProviderCredentialUseCase(
            credential_repo=mock_repo, outbox=mock_outbox
        )
        result = await uc.execute(
            CreateProviderCredentialInput(
                project_id=project_id,
                provider="openai",
                name="OpenAI Key",
                secret="sk-xxx",
            )
        )

        assert result.name == "default"
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()


class TestCreateAgentUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        project_id = uuid6.uuid7()
        credential_id = uuid6.uuid7()

        mock_agent_repo = mocker.AsyncMock()
        mock_agent_repo.save.return_value = make_agent(
            project_id=project_id, name="Helper"
        )

        mock_credential_repo = mocker.AsyncMock()
        mock_credential_repo.get_by_id.return_value = make_provider_credential(
            project_id=project_id
        )

        mock_outbox = mocker.AsyncMock()

        uc = CreateAgentUseCase(
            agent_repo=mock_agent_repo,
            credential_repo=mock_credential_repo,
            outbox=mock_outbox,
        )
        result = await uc.execute(
            CreateAgentInput(
                project_id=project_id,
                provider_credential_id=credential_id,
                name="Helper",
                model="gpt-4",
            )
        )

        assert result.name == "Helper"
        mock_agent_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_success_without_credential(self, mocker):
        project_id = uuid6.uuid7()

        mock_agent_repo = mocker.AsyncMock()
        mock_agent_repo.save.return_value = make_agent(
            project_id=project_id, name="Helper"
        )

        mock_credential_repo = mocker.AsyncMock()

        mock_outbox = mocker.AsyncMock()

        uc = CreateAgentUseCase(
            agent_repo=mock_agent_repo,
            credential_repo=mock_credential_repo,
            outbox=mock_outbox,
        )
        result = await uc.execute(
            CreateAgentInput(
                project_id=project_id,
                name="Helper",
                model="gpt-4",
            )
        )

        assert result.name == "Helper"
        mock_agent_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()
        mock_credential_repo.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_credential_not_found(self, mocker):
        project_id = uuid6.uuid7()

        mock_agent_repo = mocker.AsyncMock()

        mock_credential_repo = mocker.AsyncMock()
        mock_credential_repo.get_by_id.return_value = None

        uc = CreateAgentUseCase(
            agent_repo=mock_agent_repo,
            credential_repo=mock_credential_repo,
            outbox=mocker.AsyncMock(),
        )
        with pytest.raises(CredentialNotFoundError):
            await uc.execute(
                CreateAgentInput(
                    project_id=project_id,
                    provider_credential_id=uuid6.uuid7(),
                    name="Helper",
                    model="gpt-4",
                )
            )
        mock_agent_repo.save.assert_not_called()
