from modules.identity.domain.errors import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    OrganizationNotFoundError,
    UserNotFoundError,
)


class TestEmailAlreadyExistsError:
    def test_is_exception(self):
        assert issubclass(EmailAlreadyExistsError, Exception)

    def test_default_message(self):
        err = EmailAlreadyExistsError("Email already taken")
        assert str(err) == "Email already taken"


class TestOrganizationNotFoundError:
    def test_is_exception(self):
        assert issubclass(OrganizationNotFoundError, Exception)

    def test_default_message(self):
        err = OrganizationNotFoundError("Organization not found")
        assert str(err) == "Organization not found"


class TestUserNotFoundError:
    def test_is_exception(self):
        assert issubclass(UserNotFoundError, Exception)

    def test_default_message(self):
        err = UserNotFoundError("User not found")
        assert str(err) == "User not found"


class TestInvalidCredentialsError:
    def test_is_exception(self):
        assert issubclass(InvalidCredentialsError, Exception)

    def test_default_message(self):
        err = InvalidCredentialsError("Invalid credentials")
        assert str(err) == "Invalid credentials"
