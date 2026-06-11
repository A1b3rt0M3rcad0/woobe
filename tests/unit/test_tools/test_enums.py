from enum import StrEnum

from modules.tools.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType


class TestToolType:
    def test_values(self):
        assert ToolType.FUNCTION == "function"
        assert ToolType.API == "api"
        assert ToolType.DATABASE_QUERY == "database_query"
        assert ToolType.WEBHOOK == "webhook"
        assert ToolType.FILE_OPERATION == "file_operation"
        assert ToolType.CODE_EXECUTION == "code_execution"
        assert ToolType.CUSTOM == "custom"

    def test_is_strenum(self):
        assert issubclass(ToolType, StrEnum)

    def test_members(self):
        assert len(ToolType) == 8


class TestRiskLevel:
    def test_values(self):
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"

    def test_is_strenum(self):
        assert issubclass(RiskLevel, StrEnum)

    def test_members(self):
        assert len(RiskLevel) == 4


class TestSecretType:
    def test_values(self):
        assert SecretType.API_KEY == "api_key"
        assert SecretType.OAUTH_TOKEN == "oauth_token"
        assert SecretType.BASIC_AUTH == "basic_auth"
        assert SecretType.CERTIFICATE == "certificate"
        assert SecretType.CUSTOM == "custom"

    def test_is_strenum(self):
        assert issubclass(SecretType, StrEnum)

    def test_members(self):
        assert len(SecretType) == 5


class TestToolStatus:
    def test_values(self):
        assert ToolStatus.ACTIVE == "active"
        assert ToolStatus.INACTIVE == "inactive"
        assert ToolStatus.DEPRECATED == "deprecated"
        assert ToolStatus.DISABLED == "disabled"

    def test_is_strenum(self):
        assert issubclass(ToolStatus, StrEnum)

    def test_members(self):
        assert len(ToolStatus) == 4
