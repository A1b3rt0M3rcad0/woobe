from modules.tools.domain.enums import (
    RiskLevel,
    SecretType,
    ToolStatus,
    ToolType,
)


class TestToolType:
    def test_all_values(self):
        values = {v.value for v in ToolType}
        assert values == {"function", "http_mcp", "api", "database_query", "webhook", "file_operation", "code_execution", "custom"}


class TestRiskLevel:
    def test_all_values(self):
        values = {v.value for v in RiskLevel}
        assert values == {"low", "medium", "high", "critical"}


class TestSecretType:
    def test_all_values(self):
        values = {v.value for v in SecretType}
        assert values == {"api_key", "oauth_token", "basic_auth", "certificate", "custom"}


class TestToolStatus:
    def test_all_values(self):
        values = {v.value for v in ToolStatus}
        assert values == {"active", "inactive", "deprecated", "disabled"}
