from uuid import UUID

from modules.core.domain.enums import ApiKeyStatus, ProjectStatus
from modules.core.application.dtos import (
    CreateApiKeyInput,
    CreateApiKeyOutput,
    CreateProjectInput,
    CreateProjectOutput,
)


class TestCreateProjectInput:
    def test_creation(self):
        oid = UUID("00000000-0000-0000-0000-000000000001")
        dto = CreateProjectInput(workspace_id=oid, name="MyProj", slug="my-proj")
        assert dto.workspace_id == oid
        assert dto.name == "MyProj"
        assert dto.slug == "my-proj"

    def test_field_presence(self):
        fields = CreateProjectInput.model_fields
        assert "workspace_id" in fields
        assert "name" in fields
        assert "slug" in fields


class TestCreateProjectOutput:
    def test_creation(self):
        oid = UUID("00000000-0000-0000-0000-000000000002")
        dto = CreateProjectOutput(
            id=UUID("00000000-0000-0000-0000-000000000003"),
            workspace_id=oid,
            name="MyProj",
            slug="my-proj",
            status=ProjectStatus.active,
            created_at="2025-01-01T00:00:00Z",
        )
        assert dto.workspace_id == oid
        assert dto.name == "MyProj"
        assert dto.slug == "my-proj"
        assert dto.status == ProjectStatus.active

    def test_field_presence(self):
        fields = CreateProjectOutput.model_fields
        assert "id" in fields
        assert "workspace_id" in fields
        assert "name" in fields
        assert "slug" in fields
        assert "status" in fields
        assert "created_at" in fields


class TestCreateApiKeyInput:
    def test_creation(self):
        pid = UUID("00000000-0000-0000-0000-000000000004")
        uid = UUID("00000000-0000-0000-0000-000000000005")
        dto = CreateApiKeyInput(
            project_id=pid,
            name="MyKey",
            scopes=["reading"],
            created_by_user_id=uid,
        )
        assert dto.project_id == pid
        assert dto.name == "MyKey"
        assert dto.scopes == ["reading"]
        assert dto.created_by_user_id == uid

    def test_scopes_are_required(self):
        assert CreateApiKeyInput.model_fields["scopes"].is_required()

    def test_field_presence(self):
        fields = CreateApiKeyInput.model_fields
        assert "project_id" in fields
        assert "name" in fields
        assert "scopes" in fields
        assert "created_by_user_id" in fields


class TestCreateApiKeyOutput:
    def test_creation(self):
        dto = CreateApiKeyOutput(
            id=UUID("00000000-0000-0000-0000-000000000006"),
            project_id=UUID("00000000-0000-0000-0000-000000000007"),
            credential_id=UUID("00000000-0000-0000-0000-000000000008"),
            name="MyKey",
            key_prefix="rai_abc123",
            key_hash=b"hash",
            status=ApiKeyStatus.active,
            created_at="2025-01-01T00:00:00Z",
        )
        assert dto.key_prefix == "rai_abc123"
        assert dto.key_hash == b"hash"
        assert dto.status == ApiKeyStatus.active

    def test_field_presence(self):
        fields = CreateApiKeyOutput.model_fields
        assert "id" in fields
        assert "project_id" in fields
        assert "credential_id" in fields
        assert "name" in fields
        assert "key_prefix" in fields
        assert "key_hash" in fields
        assert "status" in fields
        assert "created_at" in fields
