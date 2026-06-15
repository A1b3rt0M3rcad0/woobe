import pytest

from shared.infra.errors import DomainError, NotFoundError, ConflictError, ValidationError


class TestDomainError:
    def test_is_exception(self):
        assert issubclass(DomainError, Exception)

    def test_can_be_raised(self):
        with pytest.raises(DomainError):
            raise DomainError("domain error")

    def test_message(self):
        err = DomainError("something went wrong")
        assert str(err) == "something went wrong"


class TestNotFoundError:
    def test_inheritance(self):
        assert issubclass(NotFoundError, DomainError)

    def test_can_be_raised(self):
        with pytest.raises(NotFoundError):
            raise NotFoundError("not found")

    def test_caught_as_domain_error(self):
        with pytest.raises(DomainError):
            raise NotFoundError("not found")


class TestConflictError:
    def test_inheritance(self):
        assert issubclass(ConflictError, DomainError)

    def test_can_be_raised(self):
        with pytest.raises(ConflictError):
            raise ConflictError("conflict")

    def test_caught_as_domain_error(self):
        with pytest.raises(DomainError):
            raise ConflictError("conflict")


class TestValidationError:
    def test_inheritance(self):
        assert issubclass(ValidationError, DomainError)

    def test_can_be_raised(self):
        with pytest.raises(ValidationError):
            raise ValidationError("invalid")

    def test_caught_as_domain_error(self):
        with pytest.raises(DomainError):
            raise ValidationError("invalid")
