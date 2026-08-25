from uuid import UUID

from modules.identity.domain.enums import (
    InviteStatus,
    MemberRole,
    MemberStatus,
    WorkspaceStatus,
    UserStatus,
)
from modules.identity.application.dtos import (
    AddMemberInput,
    AddMemberOutput,
    CreateWorkspaceInput,
    CreateWorkspaceOutput,
    CreateUserInput,
    CreateUserOutput,
    InviteUserInput,
    InviteUserOutput,
)


class TestCreateUserInput:
    def test_creation(self):
        dto = CreateUserInput(email="a@b.com", password="s3cret")
        assert dto.email == "a@b.com"
        assert dto.password == "s3cret"

    def test_field_presence(self):
        fields = CreateUserInput.model_fields
        assert "email" in fields
        assert "password" in fields


class TestCreateUserOutput:
    def test_creation(self):
        uid = UUID("00000000-0000-0000-0000-000000000001")
        dto = CreateUserOutput(
            id=uid,
            email="a@b.com",
            status=UserStatus.active,
            created_at="2025-01-01T00:00:00Z",
        )
        assert dto.id == uid
        assert dto.email == "a@b.com"
        assert dto.status == UserStatus.active
        assert dto.created_at is not None

    def test_field_presence(self):
        fields = CreateUserOutput.model_fields
        assert "id" in fields
        assert "email" in fields
        assert "status" in fields
        assert "created_at" in fields


class TestCreateWorkspaceInput:
    def test_creation(self):
        dto = CreateWorkspaceInput(name="MyWorkspace", slug="my-workspace")
        assert dto.name == "MyWorkspace"
        assert dto.slug == "my-workspace"

    def test_field_presence(self):
        fields = CreateWorkspaceInput.model_fields
        assert "name" in fields
        assert "slug" in fields


class TestCreateWorkspaceOutput:
    def test_creation(self):
        uid = UUID("00000000-0000-0000-0000-000000000002")
        dto = CreateWorkspaceOutput(
            id=uid,
            name="MyWorkspace",
            slug="my-workspace",
            status=WorkspaceStatus.active,
            created_at="2025-01-01T00:00:00Z",
        )
        assert dto.name == "MyWorkspace"
        assert dto.slug == "my-workspace"
        assert dto.status == WorkspaceStatus.active

    def test_field_presence(self):
        fields = CreateWorkspaceOutput.model_fields
        assert "id" in fields
        assert "name" in fields
        assert "slug" in fields
        assert "status" in fields
        assert "created_at" in fields


class TestAddMemberInput:
    def test_creation(self):
        uid = UUID("00000000-0000-0000-0000-000000000003")
        oid = UUID("00000000-0000-0000-0000-000000000004")
        dto = AddMemberInput(user_id=uid, workspace_id=oid, role=MemberRole.admin)
        assert dto.user_id == uid
        assert dto.workspace_id == oid
        assert dto.role == MemberRole.admin

    def test_default_role(self):
        uid = UUID("00000000-0000-0000-0000-000000000003")
        oid = UUID("00000000-0000-0000-0000-000000000004")
        dto = AddMemberInput(user_id=uid, workspace_id=oid)
        assert dto.role == MemberRole.member

    def test_field_presence(self):
        fields = AddMemberInput.model_fields
        assert "user_id" in fields
        assert "workspace_id" in fields
        assert "role" in fields


class TestAddMemberOutput:
    def test_creation(self):
        dto = AddMemberOutput(
            id=UUID("00000000-0000-0000-0000-000000000005"),
            user_id=UUID("00000000-0000-0000-0000-000000000006"),
            workspace_id=UUID("00000000-0000-0000-0000-000000000007"),
            role=MemberRole.member,
            status=MemberStatus.active,
            joined_at="2025-01-01T00:00:00Z",
        )
        assert dto.role == MemberRole.member
        assert dto.status == MemberStatus.active

    def test_field_presence(self):
        fields = AddMemberOutput.model_fields
        assert "id" in fields
        assert "user_id" in fields
        assert "workspace_id" in fields
        assert "role" in fields
        assert "status" in fields
        assert "joined_at" in fields


class TestInviteUserInput:
    def test_creation(self):
        oid = UUID("00000000-0000-0000-0000-000000000008")
        uid = UUID("00000000-0000-0000-0000-000000000009")
        dto = InviteUserInput(
            workspace_id=oid,
            email="invite@test.com",
            role=MemberRole.viewer,
            invited_by_user_id=uid,
        )
        assert dto.workspace_id == oid
        assert dto.email == "invite@test.com"
        assert dto.role == MemberRole.viewer
        assert dto.invited_by_user_id == uid

    def test_default_role(self):
        oid = UUID("00000000-0000-0000-0000-000000000008")
        uid = UUID("00000000-0000-0000-0000-000000000009")
        dto = InviteUserInput(
            workspace_id=oid,
            email="invite@test.com",
            invited_by_user_id=uid,
        )
        assert dto.role == MemberRole.member

    def test_field_presence(self):
        fields = InviteUserInput.model_fields
        assert "workspace_id" in fields
        assert "email" in fields
        assert "role" in fields
        assert "invited_by_user_id" in fields


class TestInviteUserOutput:
    def test_creation(self):
        dto = InviteUserOutput(
            id=UUID("00000000-0000-0000-0000-000000000010"),
            workspace_id=UUID("00000000-0000-0000-0000-000000000011"),
            email="invite@test.com",
            role=MemberRole.member,
            status=InviteStatus.pending,
            expires_at="2025-01-08T00:00:00Z",
            created_at="2025-01-01T00:00:00Z",
        )
        assert dto.status == InviteStatus.pending

    def test_field_presence(self):
        fields = InviteUserOutput.model_fields
        assert "id" in fields
        assert "workspace_id" in fields
        assert "email" in fields
        assert "role" in fields
        assert "status" in fields
        assert "expires_at" in fields
        assert "created_at" in fields
