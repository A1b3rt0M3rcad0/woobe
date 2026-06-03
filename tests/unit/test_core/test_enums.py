from enum import StrEnum

from modules.core.domain.enums import ApiKeyScope, ApiKeyStatus, ProjectStatus


class TestProjectStatus:
    def test_values(self):
        assert ProjectStatus.active == "active"
        assert ProjectStatus.archived == "archived"
        assert ProjectStatus.deleted == "deleted"

    def test_is_strenum(self):
        assert issubclass(ProjectStatus, StrEnum)

    def test_members_count(self):
        assert len(ProjectStatus) == 3


class TestApiKeyStatus:
    def test_values(self):
        assert ApiKeyStatus.active == "active"
        assert ApiKeyStatus.revoked == "revoked"
        assert ApiKeyStatus.expired == "expired"

    def test_is_strenum(self):
        assert issubclass(ApiKeyStatus, StrEnum)

    def test_members_count(self):
        assert len(ApiKeyStatus) == 3


class TestApiKeyScope:
    def test_values(self):
        assert ApiKeyScope.reading == "reading"
        assert ApiKeyScope.writing == "writing"
        assert ApiKeyScope.admin == "admin"
        assert ApiKeyScope.custom == "custom"

    def test_is_strenum(self):
        assert issubclass(ApiKeyScope, StrEnum)

    def test_members_count(self):
        assert len(ApiKeyScope) == 4
