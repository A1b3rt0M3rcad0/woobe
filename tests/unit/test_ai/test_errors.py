from modules.ai.domain.errors import AgentNotFoundError, CredentialNotFoundError
from shared.domain.errors import DomainError, NotFoundError


class TestCredentialNotFoundError:
    def test_inheritance(self):
        err = CredentialNotFoundError("cred-id")
        assert isinstance(err, Exception)
        assert isinstance(err, DomainError)
        assert isinstance(err, NotFoundError)
        assert isinstance(err, CredentialNotFoundError)

    def test_message_format(self):
        err = CredentialNotFoundError("cred-123")
        assert "cred-123" in str(err)


class TestAgentNotFoundError:
    def test_inheritance(self):
        err = AgentNotFoundError("agent-id")
        assert isinstance(err, Exception)
        assert isinstance(err, DomainError)
        assert isinstance(err, NotFoundError)
        assert isinstance(err, AgentNotFoundError)

    def test_message_format(self):
        err = AgentNotFoundError("agent-456")
        assert "agent-456" in str(err)
