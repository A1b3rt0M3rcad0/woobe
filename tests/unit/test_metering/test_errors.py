import pytest

from modules.metering.domain.errors import UsageEventNotFoundError
from shared.infra.errors import NotFoundError, DomainError


class TestUsageEventNotFoundError:
    def test_inheritance(self):
        err = UsageEventNotFoundError("not found")
        assert isinstance(err, UsageEventNotFoundError)
        assert isinstance(err, NotFoundError)
        assert isinstance(err, DomainError)
        assert isinstance(err, Exception)

    def test_message(self):
        err = UsageEventNotFoundError("usage event not found")
        assert str(err) == "usage event not found"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(UsageEventNotFoundError):
            raise UsageEventNotFoundError("test")
