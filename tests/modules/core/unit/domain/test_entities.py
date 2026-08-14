from uuid import UUID

from modules.core.domain.entities import ApiKey, Project
from modules.core.domain.enums import ApiKeyStatus, ProjectStatus


class TestProject:
    def test_create_with_defaults(self):
        project = Project()
        assert isinstance(project.id, UUID)
        assert isinstance(project.workspace_id, UUID)
        assert project.name == ""
        assert project.slug == ""
        assert project.status == ProjectStatus.active
        assert project.data == {}
        assert project.created_at is None
        assert project.updated_at is None

    def test_create_with_values(self):
        project = Project(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            workspace_id=UUID("00000000-0000-0000-0000-000000000002"),
            name="Test Project",
            slug="test-project",
            status=ProjectStatus.active,
        )
        assert project.id == UUID("00000000-0000-0000-0000-000000000001")
        assert project.workspace_id == UUID("00000000-0000-0000-0000-000000000002")
        assert project.name == "Test Project"
        assert project.slug == "test-project"
        assert project.status == ProjectStatus.active


class TestApiKey:
    def test_create_with_defaults(self):
        key = ApiKey()
        assert isinstance(key.id, UUID)
        assert isinstance(key.project_id, UUID)
        assert key.name == ""
        assert key.key_prefix == ""
        assert key.key_hash == b""
        assert key.scopes == []
        assert key.status == ApiKeyStatus.active
        assert key.last_used_at is None
        assert key.expires_at is None
        assert key.revoked_at is None
        assert isinstance(key.created_by_user_id, UUID)
        assert key.created_at is None
        assert key.updated_at is None

    def test_create_with_values(self):
        key = ApiKey(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            project_id=UUID("00000000-0000-0000-0000-000000000002"),
            name="Test Key",
            key_prefix="rai_abc123",
            key_hash=b"\x00" * 32,
            scopes=["reading"],
            status=ApiKeyStatus.active,
            created_by_user_id=UUID("00000000-0000-0000-0000-000000000003"),
        )
        assert key.name == "Test Key"
        assert key.key_prefix == "rai_abc123"
        assert key.key_hash == b"\x00" * 32
        assert key.scopes == ["reading"]
        assert key.status == ApiKeyStatus.active
