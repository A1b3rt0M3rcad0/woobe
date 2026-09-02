import pytest

from modules.observability.domain.errors import TraceNotFoundError
from shared.contracts.errors import DomainError, NotFoundError


class TestTraceNotFoundError:
    def test_inheritance(self):
        err = TraceNotFoundError("trace not found")
        assert isinstance(err, TraceNotFoundError)
        assert isinstance(err, NotFoundError)
        assert isinstance(err, DomainError)
        assert isinstance(err, Exception)

    def test_message(self):
        err = TraceNotFoundError("Trace abc-123 not found")
        assert str(err) == "Trace abc-123 not found"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(TraceNotFoundError):
            raise TraceNotFoundError("test")
