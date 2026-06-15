from modules.core.domain.enums import ApiKeyScope, ApiKeyStatus, ProjectStatus


class TestProjectStatus:
    def test_active_has_correct_value(self):
        assert ProjectStatus.active.value == "active"

    def test_all_values(self):
        values = {s.value for s in ProjectStatus}
        assert values == {"active", "archived", "deleted"}


class TestApiKeyStatus:
    def test_active_has_correct_value(self):
        assert ApiKeyStatus.active.value == "active"

    def test_all_values(self):
        values = {s.value for s in ApiKeyStatus}
        assert values == {"active", "revoked", "expired"}


class TestApiKeyScope:
    def test_all_values(self):
        values = {s.value for s in ApiKeyScope}
        assert values == {"reading", "writing", "admin", "custom"}
