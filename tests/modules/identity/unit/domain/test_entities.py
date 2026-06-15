from uuid import UUID
from datetime import datetime, timezone

from modules.identity.domain.entities import (
    User,
    Organization,
    OrganizationMember,
    OrganizationInvite,
    UserSession,
)
from modules.identity.domain.enums import (
    InviteStatus,
    MemberRole,
    MemberStatus,
    OrganizationStatus,
    UserSessionStatus,
    UserStatus,
)


class TestUser:
    def test_create_with_defaults(self):
        user = User()
        assert isinstance(user.id, UUID)
        assert user.email == ""
        assert user.password == b""
        assert user.status == UserStatus.active
        assert user.created_at is None
        assert user.updated_at is None

    def test_create_with_values(self):
        now = datetime.now(timezone.utc)
        user = User(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            email="test@example.com",
            password=b"hashed",
            status=UserStatus.active,
            created_at=now,
            updated_at=now,
        )
        assert user.id == UUID("00000000-0000-0000-0000-000000000001")
        assert user.email == "test@example.com"
        assert user.password == b"hashed"
        assert user.status == UserStatus.active


class TestOrganization:
    def test_create_with_defaults(self):
        org = Organization()
        assert isinstance(org.id, UUID)
        assert org.name == ""
        assert org.slug == ""
        assert org.status == OrganizationStatus.active

    def test_create_with_values(self):
        org = Organization(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            name="Test Org",
            slug="test-org",
        )
        assert org.name == "Test Org"
        assert org.slug == "test-org"

    def test_active_by_default(self):
        org = Organization()
        assert org.status == OrganizationStatus.active


class TestOrganizationMember:
    def test_create_with_defaults(self):
        member = OrganizationMember()
        assert isinstance(member.id, UUID)
        assert member.role == MemberRole.member
        assert member.status == MemberStatus.active


class TestOrganizationInvite:
    def test_create_with_defaults(self):
        invite = OrganizationInvite()
        assert isinstance(invite.id, UUID)
        assert invite.status == InviteStatus.pending
        assert invite.role == MemberRole.member

    def test_create_with_values(self):
        invite = OrganizationInvite(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            email="invite@example.com",
            role=MemberRole.admin,
        )
        assert invite.email == "invite@example.com"
        assert invite.role == MemberRole.admin


class TestUserSession:
    def test_create_with_defaults(self):
        session = UserSession()
        assert isinstance(session.id, UUID)
        assert session.status == UserSessionStatus.active

    def test_create_with_values(self):
        now = datetime.now(timezone.utc)
        session = UserSession(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=UUID("00000000-0000-0000-0000-000000000002"),
            refresh_token_hash=b"token",
            user_agent="Mozilla/5.0",
            ip_address="127.0.0.1",
            expires_at=now,
        )
        assert session.user_agent == "Mozilla/5.0"
        assert session.ip_address == "127.0.0.1"
