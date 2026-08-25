import uuid6
from datetime import datetime
from uuid import UUID

from modules.core.domain.entities import ApiKey, Project
from modules.core.domain.enums import ApiKeyStatus, ProjectStatus


class TestProject:
    def test_default_creation(self):
        p = Project()
        assert isinstance(p.id, UUID)
        assert isinstance(p.workspace_id, UUID)
        assert p.name == ""
        assert p.slug == ""
        assert p.status == ProjectStatus.active
        assert p.data == {}
        assert p.created_at is None
        assert p.updated_at is None

    def test_field_types(self):
        now = datetime.now()
        p = Project(
            id=uuid6.uuid7(),
            workspace_id=uuid6.uuid7(),
            name="MyProject",
            slug="my-project",
            status=ProjectStatus.archived,
            data={"key": "value"},
            created_at=now,
            updated_at=now,
        )
        assert isinstance(p.id, UUID)
        assert isinstance(p.workspace_id, UUID)
        assert isinstance(p.name, str)
        assert isinstance(p.slug, str)
        assert isinstance(p.status, ProjectStatus)
        assert isinstance(p.data, dict)
        assert isinstance(p.created_at, datetime)

    def test_uuid_generation(self):
        p1 = Project()
        p2 = Project()
        assert p1.id != p2.id


class TestApiKey:
    def test_default_creation(self):
        k = ApiKey()
        assert isinstance(k.id, UUID)
        assert isinstance(k.project_id, UUID)
        assert k.name == ""
        assert k.key_prefix == ""
        assert k.key_hash == b""
        assert k.scopes == []
        assert k.status == ApiKeyStatus.active
        assert k.last_used_at is None
        assert k.expires_at is None
        assert k.revoked_at is None
        assert isinstance(k.created_by_user_id, UUID)
        assert k.created_at is None
        assert k.updated_at is None

    def test_field_types(self):
        now = datetime.now()
        k = ApiKey(
            id=uuid6.uuid7(),
            project_id=uuid6.uuid7(),
            name="MyKey",
            key_prefix="rai_abc123",
            key_hash=b"hash",
            scopes=["reading", "writing"],
            status=ApiKeyStatus.revoked,
            last_used_at=now,
            expires_at=now,
            revoked_at=now,
            created_by_user_id=uuid6.uuid7(),
            created_at=now,
            updated_at=now,
        )
        assert isinstance(k.key_prefix, str)
        assert isinstance(k.key_hash, bytes)
        assert isinstance(k.scopes, list)
        assert isinstance(k.status, ApiKeyStatus)

    def test_uuid_generation(self):
        k1 = ApiKey()
        k2 = ApiKey()
        assert k1.id != k2.id
