import uuid6
from datetime import datetime
from uuid import UUID

from modules.identity.domain.entities import (
    Workspace,
    WorkspaceInvite,
    WorkspaceMember,
    User,
    UserSession,
)
from modules.identity.domain.enums import (
    InviteStatus,
    MemberRole,
    MemberStatus,
    WorkspaceStatus,
    UserSessionStatus,
    UserStatus,
)


class TestUser:
    def test_default_creation(self):
        user = User()
        assert isinstance(user.id, UUID)
        assert user.email == ""
        assert user.password == b""
        assert user.status == UserStatus.active
        assert user.created_at is None
        assert user.updated_at is None

    def test_field_types(self):
        now = datetime.now()
        user = User(
            id=uuid6.uuid7(),
            email="test@test.com",
            password=b"hash",
            status=UserStatus.suspended,
            created_at=now,
            updated_at=now,
        )
        assert isinstance(user.id, UUID)
        assert isinstance(user.email, str)
        assert isinstance(user.password, bytes)
        assert isinstance(user.status, UserStatus)
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)

    def test_uuid_generation(self):
        user1 = User()
        user2 = User()
        assert user1.id != user2.id


class TestWorkspace:
    def test_default_creation(self):
        workspace = Workspace()
        assert isinstance(workspace.id, UUID)
        assert workspace.name == ""
        assert workspace.slug == ""
        assert workspace.status == WorkspaceStatus.active
        assert workspace.created_at is None
        assert workspace.updated_at is None

    def test_field_types(self):
        now = datetime.now()
        workspace = Workspace(
            id=uuid6.uuid7(),
            name="MyWorkspace",
            slug="my-workspace",
            status=WorkspaceStatus.suspended,
            created_at=now,
            updated_at=now,
        )
        assert isinstance(workspace.id, UUID)
        assert isinstance(workspace.name, str)
        assert isinstance(workspace.slug, str)
        assert isinstance(workspace.status, WorkspaceStatus)
        assert isinstance(workspace.created_at, datetime)

    def test_uuid_generation(self):
        o1 = Workspace()
        o2 = Workspace()
        assert o1.id != o2.id


class TestWorkspaceMember:
    def test_default_creation(self):
        m = WorkspaceMember()
        assert isinstance(m.id, UUID)
        assert isinstance(m.user_id, UUID)
        assert isinstance(m.workspace_id, UUID)
        assert m.role == MemberRole.member
        assert m.status == MemberStatus.active
        assert m.joined_at is None
        assert m.created_at is None
        assert m.updated_at is None

    def test_field_types(self):
        now = datetime.now()
        m = WorkspaceMember(
            id=uuid6.uuid7(),
            user_id=uuid6.uuid7(),
            workspace_id=uuid6.uuid7(),
            role=MemberRole.admin,
            status=MemberStatus.inactive,
            joined_at=now,
            created_at=now,
            updated_at=now,
        )
        assert isinstance(m.role, MemberRole)
        assert isinstance(m.status, MemberStatus)

    def test_uuid_generation(self):
        m1 = WorkspaceMember()
        m2 = WorkspaceMember()
        assert m1.id != m2.id


class TestWorkspaceInvite:
    def test_default_creation(self):
        inv = WorkspaceInvite()
        assert isinstance(inv.id, UUID)
        assert isinstance(inv.workspace_id, UUID)
        assert inv.email == ""
        assert inv.role == MemberRole.member
        assert inv.token_hash == ""
        assert isinstance(inv.invited_by_user_id, UUID)
        assert inv.status == InviteStatus.pending
        assert inv.expires_at is None
        assert inv.accepted_at is None
        assert inv.created_at is None
        assert inv.updated_at is None

    def test_field_types(self):
        now = datetime.now()
        inv = WorkspaceInvite(
            id=uuid6.uuid7(),
            workspace_id=uuid6.uuid7(),
            email="invite@test.com",
            role=MemberRole.viewer,
            token_hash="abc123",
            invited_by_user_id=uuid6.uuid7(),
            status=InviteStatus.accepted,
            expires_at=now,
            accepted_at=now,
            created_at=now,
            updated_at=now,
        )
        assert isinstance(inv.role, MemberRole)
        assert isinstance(inv.status, InviteStatus)

    def test_uuid_generation(self):
        i1 = WorkspaceInvite()
        i2 = WorkspaceInvite()
        assert i1.id != i2.id


class TestUserSession:
    def test_default_creation(self):
        s = UserSession()
        assert isinstance(s.id, UUID)
        assert isinstance(s.user_id, UUID)
        assert s.refresh_token_hash == b""
        assert s.user_agent is None
        assert s.ip_address is None
        assert s.status == UserSessionStatus.active
        assert s.revoked_at is None
        assert s.expires_at is None
        assert s.last_used_at is None
        assert s.created_at is None
        assert s.updated_at is None

    def test_field_types(self):
        now = datetime.now()
        s = UserSession(
            id=uuid6.uuid7(),
            user_id=uuid6.uuid7(),
            refresh_token_hash=b"hash",
            user_agent="Mozilla/5.0",
            ip_address="127.0.0.1",
            status=UserSessionStatus.expired,
            revoked_at=now,
            expires_at=now,
            last_used_at=now,
            created_at=now,
            updated_at=now,
        )
        assert isinstance(s.refresh_token_hash, bytes)
        assert isinstance(s.user_agent, str)
        assert isinstance(s.ip_address, str)
        assert isinstance(s.status, UserSessionStatus)

    def test_uuid_generation(self):
        s1 = UserSession()
        s2 = UserSession()
        assert s1.id != s2.id
