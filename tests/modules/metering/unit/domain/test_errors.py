from modules.metering.domain.errors import UsageEventNotFoundError


class TestUsageEventNotFoundError:
    def test_is_exception(self):
        assert issubclass(UsageEventNotFoundError, Exception)

    def test_default_message(self):
        err = UsageEventNotFoundError("Usage event not found")
        assert str(err) == "Usage event not found"
