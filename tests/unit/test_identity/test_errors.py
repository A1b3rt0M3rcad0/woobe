from modules.identity.domain.errors import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    WorkspaceNotFoundError,
    UserNotFoundError,
)
from shared.infra.errors import ConflictError, DomainError, NotFoundError


class TestEmailAlreadyExistsError:
    def test_inheritance(self):
        err = EmailAlreadyExistsError("test@test.com")
        assert isinstance(err, Exception)
        assert isinstance(err, DomainError)
        assert isinstance(err, ConflictError)
        assert isinstance(err, EmailAlreadyExistsError)

    def test_message_format(self):
        err = EmailAlreadyExistsError("user@test.com")
        assert "user@test.com" in str(err)


class TestWorkspaceNotFoundError:
    def test_inheritance(self):
        err = WorkspaceNotFoundError("workspace-id")
        assert isinstance(err, Exception)
        assert isinstance(err, DomainError)
        assert isinstance(err, NotFoundError)
        assert isinstance(err, WorkspaceNotFoundError)

    def test_message_format(self):
        err = WorkspaceNotFoundError("workspace-123")
        assert "workspace-123" in str(err)


class TestUserNotFoundError:
    def test_inheritance(self):
        err = UserNotFoundError("user-id")
        assert isinstance(err, Exception)
        assert isinstance(err, DomainError)
        assert isinstance(err, NotFoundError)
        assert isinstance(err, UserNotFoundError)

    def test_message_format(self):
        err = UserNotFoundError("usr-456")
        assert "usr-456" in str(err)


class TestInvalidCredentialsError:
    def test_inheritance(self):
        err = InvalidCredentialsError()
        assert isinstance(err, Exception)
        assert isinstance(err, DomainError)
        assert isinstance(err, NotFoundError)
        assert isinstance(err, InvalidCredentialsError)

    def test_message_format(self):
        err = InvalidCredentialsError("Invalid email or password")
        assert "Invalid email or password" in str(err)
