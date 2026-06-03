from enum import StrEnum

from modules.ai.domain.enums import (
    AgentStatus,
    AgentType,
    CredentialStatus,
    Provider,
    SessionMode,
)


class TestProvider:
    def test_values(self):
        assert Provider.openai == "openai"
        assert Provider.anthropic == "anthropic"
        assert Provider.google == "google"
        assert Provider.azure == "azure"
        assert Provider.aws_bedrock == "aws_bedrock"
        assert Provider.groq == "groq"

    def test_is_strenum(self):
        assert issubclass(Provider, StrEnum)

    def test_members_count(self):
        assert len(Provider) == 6


class TestCredentialStatus:
    def test_values(self):
        assert CredentialStatus.active == "active"
        assert CredentialStatus.expired == "expired"
        assert CredentialStatus.revoked == "revoked"
        assert CredentialStatus.invalid == "invalid"

    def test_is_strenum(self):
        assert issubclass(CredentialStatus, StrEnum)

    def test_members_count(self):
        assert len(CredentialStatus) == 4


class TestAgentStatus:
    def test_values(self):
        assert AgentStatus.active == "active"
        assert AgentStatus.inactive == "inactive"
        assert AgentStatus.archived == "archived"

    def test_is_strenum(self):
        assert issubclass(AgentStatus, StrEnum)

    def test_members_count(self):
        assert len(AgentStatus) == 3


class TestSessionMode:
    def test_values(self):
        assert SessionMode.stateless == "stateless"
        assert SessionMode.stateful == "stateful"

    def test_is_strenum(self):
        assert issubclass(SessionMode, StrEnum)

    def test_members_count(self):
        assert len(SessionMode) == 2


class TestAgentType:
    def test_values(self):
        assert AgentType.chat == "chat"
        assert AgentType.completion == "completion"
        assert AgentType.assistant == "assistant"
        assert AgentType.custom == "custom"

    def test_is_strenum(self):
        assert issubclass(AgentType, StrEnum)

    def test_members_count(self):
        assert len(AgentType) == 4
