from uuid import UUID

from modules.tools.domain.entities import Secret, Tool
from modules.tools.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType


class TestTool:
    def test_create_with_defaults(self):
        tool = Tool()
        assert isinstance(tool.id, UUID)
        assert tool.name == ""
        assert tool.type == ToolType.FUNCTION
        assert tool.risk_level == RiskLevel.LOW
        assert tool.status == ToolStatus.ACTIVE
        assert tool.created_at is None
        assert tool.updated_at is None

    def test_create_with_values(self):
        tool = Tool(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            project_id=UUID("00000000-0000-0000-0000-000000000002"),
            name="test-tool",
            type=ToolType.API,
            config={"url": "https://example.com"},
            risk_level=RiskLevel.MEDIUM,
            timeout_ms=5000,
            status=ToolStatus.ACTIVE,
        )
        assert tool.id == UUID("00000000-0000-0000-0000-000000000001")
        assert tool.project_id == UUID("00000000-0000-0000-0000-000000000002")
        assert tool.name == "test-tool"
        assert tool.type == ToolType.API
        assert tool.config == {"url": "https://example.com"}
        assert tool.risk_level == RiskLevel.MEDIUM
        assert tool.timeout_ms == 5000
        assert tool.status == ToolStatus.ACTIVE

    def test_default_type_is_function(self):
        tool = Tool()
        assert tool.type == ToolType.FUNCTION

    def test_default_risk_is_low(self):
        tool = Tool()
        assert tool.risk_level == RiskLevel.LOW

    def test_default_status_is_active(self):
        tool = Tool()
        assert tool.status == ToolStatus.ACTIVE


class TestSecret:
    def test_create_with_defaults(self):
        secret = Secret()
        assert isinstance(secret.id, UUID)
        assert secret.name == ""
        assert secret.type == SecretType.CUSTOM
        assert secret.encrypted_value == ""
        assert secret.data is None
        assert secret.created_at is None
        assert secret.updated_at is None

    def test_create_with_values(self):
        secret = Secret(
            id=UUID("00000000-0000-0000-0000-000000000003"),
            project_id=UUID("00000000-0000-0000-0000-000000000002"),
            name="api-key",
            type=SecretType.API_KEY,
            encrypted_value="encrypted",
            data={"key": "value"},
        )
        assert secret.id == UUID("00000000-0000-0000-0000-000000000003")
        assert secret.project_id == UUID("00000000-0000-0000-0000-000000000002")
        assert secret.name == "api-key"
        assert secret.type == SecretType.API_KEY
        assert secret.encrypted_value == "encrypted"
        assert secret.data == {"key": "value"}

    def test_default_secret_type(self):
        secret = Secret()
        assert secret.type == SecretType.CUSTOM
