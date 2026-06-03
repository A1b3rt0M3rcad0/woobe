from modules.identity.domain.errors import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    OrganizationNotFoundError,
    UserNotFoundError,
)
from shared.domain.errors import ConflictError, DomainError, NotFoundError


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


class TestOrganizationNotFoundError:
    def test_inheritance(self):
        err = OrganizationNotFoundError("org-id")
        assert isinstance(err, Exception)
        assert isinstance(err, DomainError)
        assert isinstance(err, NotFoundError)
        assert isinstance(err, OrganizationNotFoundError)

    def test_message_format(self):
        err = OrganizationNotFoundError("org-123")
        assert "org-123" in str(err)


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
