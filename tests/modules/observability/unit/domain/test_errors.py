from modules.observability.domain.errors import TraceNotFoundError


class TestTraceNotFoundError:
    def test_is_exception(self):
        assert issubclass(TraceNotFoundError, Exception)

    def test_default_message(self):
        err = TraceNotFoundError("Trace not found")
        assert str(err) == "Trace not found"
