import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from modules.tools.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType
from modules.tools.service.dtos import CreateSecretInput, CreateSecretOutput, CreateToolInput, CreateToolOutput


class TestCreateToolInput:
    def test_valid(self):
        pid = uuid.uuid4()
        aid = uuid.uuid4()
        dto = CreateToolInput(project_id=pid, agent_id=aid, name="search-tool")
        assert dto.project_id == pid
        assert dto.agent_id == aid
        assert dto.name == "search-tool"
        assert dto.type == ToolType.FUNCTION
        assert dto.risk_level == RiskLevel.LOW
        assert dto.description is None
        assert dto.config is None
        assert dto.input_schema is None
        assert dto.output_schema is None
        assert dto.timeout_ms is None

    def test_with_all_fields(self):
        dto = CreateToolInput(
            project_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            name="api-tool",
            description="Calls external API",
            type=ToolType.API,
            config={"url": "https://api.example.com"},
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            risk_level=RiskLevel.HIGH,
            timeout_ms=10000,
        )
        assert dto.description == "Calls external API"
        assert dto.type == ToolType.API
        assert dto.config == {"url": "https://api.example.com"}
        assert dto.risk_level == RiskLevel.HIGH
        assert dto.timeout_ms == 10000

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            CreateToolInput(
                project_id=uuid.uuid4(),
                agent_id=uuid.uuid4(),
                name="",
            )


class TestCreateToolOutput:
    def test_valid(self):
        now = datetime.now(timezone.utc)
        dto = CreateToolOutput(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            name="search-tool",
            description=None,
            type=ToolType.FUNCTION,
            config=None,
            input_schema=None,
            output_schema=None,
            risk_level=RiskLevel.LOW,
            timeout_ms=None,
            status=ToolStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        assert dto.name == "search-tool"
        assert dto.type == ToolType.FUNCTION
        assert dto.status == ToolStatus.ACTIVE
        assert dto.risk_level == RiskLevel.LOW

    def test_with_optional_fields(self):
        now = datetime.now(timezone.utc)
        dto = CreateToolOutput(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            name="api-tool",
            description="My tool",
            type=ToolType.API,
            config={"key": "val"},
            input_schema={},
            output_schema={},
            risk_level=RiskLevel.CRITICAL,
            timeout_ms=5000,
            status=ToolStatus.INACTIVE,
            created_at=now,
            updated_at=now,
        )
        assert dto.description == "My tool"
        assert dto.config == {"key": "val"}
        assert dto.risk_level == RiskLevel.CRITICAL
        assert dto.timeout_ms == 5000


class TestCreateSecretInput:
    def test_valid(self):
        pid = uuid.uuid4()
        dto = CreateSecretInput(project_id=pid, name="api-key", value="sk-123")
        assert dto.project_id == pid
        assert dto.name == "api-key"
        assert dto.value == "sk-123"
        assert dto.type == SecretType.CUSTOM
        assert dto.data is None

    def test_with_type_and_metadata(self):
        dto = CreateSecretInput(
            project_id=uuid.uuid4(),
            name="openai-key",
            type=SecretType.API_KEY,
            value="sk-xxx",
            data={"provider": "openai"},
        )
        assert dto.type == SecretType.API_KEY
        assert dto.data == {"provider": "openai"}

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            CreateSecretInput(
                project_id=uuid.uuid4(),
                name="",
                value="val",
            )

    def test_empty_value_raises(self):
        with pytest.raises(ValidationError):
            CreateSecretInput(
                project_id=uuid.uuid4(),
                name="key",
                value="",
            )


class TestCreateSecretOutput:
    def test_valid(self):
        now = datetime.now(timezone.utc)
        dto = CreateSecretOutput(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            name="api-key",
            type=SecretType.CUSTOM,
            data=None,
            created_at=now,
            updated_at=now,
        )
        assert dto.name == "api-key"
        assert dto.type == SecretType.CUSTOM
        assert dto.data is None

    def test_with_metadata(self):
        now = datetime.now(timezone.utc)
        dto = CreateSecretOutput(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            name="key",
            type=SecretType.API_KEY,
            data={"provider": "openai"},
            created_at=now,
            updated_at=now,
        )
        assert dto.data == {"provider": "openai"}
