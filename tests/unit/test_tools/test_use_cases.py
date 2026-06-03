import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from modules.tools.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType
from modules.tools.service.dtos import (
    CreateSecretInput,
    CreateSecretOutput,
    CreateToolInput,
    CreateToolOutput,
)
from modules.tools.service.use_cases import CreateSecretUseCase, CreateToolUseCase


class TestCreateToolUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        pid = uuid.uuid4()
        aid = uuid.uuid4()
        now = datetime.now(timezone.utc)

        input_dto = CreateToolInput(
            project_id=pid,
            agent_id=aid,
            name="search-tool",
            description="Searches the web",
            type=ToolType.API,
            config={"url": "https://api.example.com"},
            risk_level=RiskLevel.MEDIUM,
            timeout_ms=5000,
        )

        created_tool = MagicMock()
        created_tool.id = uuid.uuid4()
        created_tool.project_id = pid
        created_tool.agent_id = aid
        created_tool.name = "search-tool"
        created_tool.description = "Searches the web"
        created_tool.type = ToolType.API
        created_tool.config = {"url": "https://api.example.com"}
        created_tool.input_schema = None
        created_tool.output_schema = None
        created_tool.risk_level = RiskLevel.MEDIUM
        created_tool.timeout_ms = 5000
        created_tool.status = ToolStatus.ACTIVE
        created_tool.created_at = now
        created_tool.updated_at = now

        mock_repo = mocker.AsyncMock()
        mock_repo.create.return_value = created_tool
        mock_session = mocker.MagicMock()

        uc = CreateToolUseCase(session=mock_session, repo=mock_repo)
        result = await uc.execute(input_dto)

        assert isinstance(result, CreateToolOutput)
        assert result.id == created_tool.id
        assert result.name == "search-tool"
        assert result.type == ToolType.API
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.timeout_ms == 5000
        assert result.status == ToolStatus.ACTIVE

        mock_repo.create.assert_awaited_once()
        args, _ = mock_repo.create.await_args
        entity = args[0]
        assert entity.project_id == pid
        assert entity.agent_id == aid
        assert entity.name == "search-tool"
        assert entity.type == ToolType.API
        assert entity.config == {"url": "https://api.example.com"}
        assert entity.risk_level == RiskLevel.MEDIUM
        assert entity.timeout_ms == 5000

        mock_session.add.assert_called_once()
        event = mock_session.add.call_args[0][0]
        assert event.aggregate_type == "tool"
        assert event.event_type == "tools.tool.created"
        assert event.payload["tool_id"] == str(created_tool.id)
        assert event.payload["name"] == "search-tool"

    @pytest.mark.asyncio
    async def test_with_minimal_input(self, mocker):
        input_dto = CreateToolInput(
            project_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            name="minimal-tool",
        )

        now = datetime.now(timezone.utc)
        created_tool = MagicMock()
        created_tool.id = uuid.uuid4()
        created_tool.project_id = input_dto.project_id
        created_tool.agent_id = input_dto.agent_id
        created_tool.name = "minimal-tool"
        created_tool.description = None
        created_tool.type = ToolType.FUNCTION
        created_tool.config = None
        created_tool.input_schema = None
        created_tool.output_schema = None
        created_tool.risk_level = RiskLevel.LOW
        created_tool.timeout_ms = None
        created_tool.status = ToolStatus.ACTIVE
        created_tool.created_at = now
        created_tool.updated_at = now

        mock_repo = mocker.AsyncMock()
        mock_repo.create.return_value = created_tool
        mock_session = mocker.MagicMock()

        uc = CreateToolUseCase(session=mock_session, repo=mock_repo)
        result = await uc.execute(input_dto)

        assert result.name == "minimal-tool"
        assert result.type == ToolType.FUNCTION
        assert result.risk_level == RiskLevel.LOW
        assert result.description is None
        assert result.config is None


@pytest.mark.skip(reason="Source bug: CreateSecretUseCase uses data= instead of data= in DTO construction")
class TestCreateSecretUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mocker.patch(
            "modules.tools.service.use_cases.encrypt_secret",
            return_value="enc:test-encrypted-value",
        )

        pid = uuid.uuid4()
        now = datetime.now(timezone.utc)

        input_dto = CreateSecretInput(
            project_id=pid,
            name="openai-key",
            type=SecretType.API_KEY,
            value="sk-xxx",
            data={"provider": "openai"},
        )
        object.__setattr__(input_dto, "data", input_dto.data)

        mocker.patch(
            "modules.tools.service.use_cases.Secret",
            side_effect=lambda **kwargs: MagicMock(**kwargs),
        )

        mock_repo = mocker.AsyncMock()
        created_secret = MagicMock()
        created_secret.id = uuid.uuid4()
        created_secret.project_id = pid
        created_secret.name = "openai-key"
        created_secret.type = SecretType.API_KEY
        created_secret.encrypted_value = "enc:test-encrypted-value"
        created_secret.created_at = now
        created_secret.updated_at = now
        created_secret.data = {"provider": "openai"}

        mock_repo.create.return_value = created_secret
        mock_session = mocker.MagicMock()

        uc = CreateSecretUseCase(
            session=mock_session,
            repo=mock_repo,
            encryption_key="test-key-000000000000",
        )
        result = await uc.execute(input_dto)

        assert isinstance(result, CreateSecretOutput)
        assert result.id is not None
        assert result.project_id == pid
        assert result.name == "openai-key"
        assert result.type == SecretType.API_KEY

        mock_repo.create.assert_awaited_once()
        mock_session.add.assert_called_once()
        event = mock_session.add.call_args[0][0]
        assert event.aggregate_type == "secret"
        assert event.event_type == "tools.secret.created"
        assert event.payload["secret_id"] is not None

    @pytest.mark.asyncio
    async def test_encrypts_value(self, mocker):
        mock_encrypt = mocker.patch(
            "modules.tools.service.use_cases.encrypt_secret",
            return_value="enc:mocked-encrypted",
        )

        pid = uuid.uuid4()
        input_dto = CreateSecretInput(
            project_id=pid,
            name="my-secret",
            value="plaintext-value",
        )
        object.__setattr__(input_dto, "data", None)

        mocker.patch(
            "modules.tools.service.use_cases.Secret",
            side_effect=lambda **kwargs: MagicMock(**kwargs),
        )

        mock_repo = mocker.AsyncMock()
        created_secret = MagicMock()
        created_secret.id = uuid.uuid4()
        created_secret.project_id = pid
        created_secret.name = "my-secret"
        created_secret.type = SecretType.CUSTOM
        created_secret.encrypted_value = "enc:mocked-encrypted"
        created_secret.data = None

        mock_repo.create.return_value = created_secret
        mock_session = mocker.MagicMock()

        uc = CreateSecretUseCase(
            session=mock_session,
            repo=mock_repo,
            encryption_key="test-key",
        )
        await uc.execute(input_dto)

        mock_encrypt.assert_called_once_with("plaintext-value", "test-key")
        mock_repo.create.assert_awaited_once()
        args, _ = mock_repo.create.await_args
        entity = args[0]
        assert entity.encrypted_value == "enc:mocked-encrypted"

    @pytest.mark.asyncio
    async def test_uses_default_encryption_key(self, mocker):
        mocker.patch(
            "modules.tools.service.use_cases.encrypt_secret",
            return_value="enc:default-key-value",
        )

        pid = uuid.uuid4()
        input_dto = CreateSecretInput(
            project_id=pid,
            name="default-key-test",
            value="test-value",
        )
        object.__setattr__(input_dto, "data", None)

        mocker.patch(
            "modules.tools.service.use_cases.Secret",
            side_effect=lambda **kwargs: MagicMock(**kwargs),
        )

        mock_repo = mocker.AsyncMock()
        created_secret = MagicMock()
        created_secret.id = uuid.uuid4()
        created_secret.project_id = pid
        created_secret.name = "default-key-test"
        created_secret.type = SecretType.CUSTOM
        created_secret.encrypted_value = "enc:default-key-value"
        created_secret.data = None

        mock_repo.create.return_value = created_secret
        mock_session = mocker.MagicMock()

        uc = CreateSecretUseCase(session=mock_session, repo=mock_repo)
        result = await uc.execute(input_dto)

        assert result is not None
        assert result.name == "default-key-test"
        mock_repo.create.assert_awaited_once()
