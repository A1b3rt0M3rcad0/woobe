from enum import StrEnum

from modules.identity.domain.enums import (
    InviteStatus,
    MemberRole,
    MemberStatus,
    WorkspaceStatus,
    UserSessionStatus,
    UserStatus,
)


class TestUserStatus:
    def test_values(self):
        assert UserStatus.active == "active"
        assert UserStatus.inactive == "inactive"
        assert UserStatus.suspended == "suspended"
        assert UserStatus.deleted == "deleted"

    def test_is_strenum(self):
        assert issubclass(UserStatus, StrEnum)

    def test_members_count(self):
        assert len(UserStatus) == 4


class TestWorkspaceStatus:
    def test_values(self):
        assert WorkspaceStatus.active == "active"
        assert WorkspaceStatus.inactive == "inactive"
        assert WorkspaceStatus.suspended == "suspended"

    def test_is_strenum(self):
        assert issubclass(WorkspaceStatus, StrEnum)

    def test_members_count(self):
        assert len(WorkspaceStatus) == 3


class TestMemberRole:
    def test_values(self):
        assert MemberRole.owner == "owner"
        assert MemberRole.admin == "admin"
        assert MemberRole.member == "member"
        assert MemberRole.viewer == "viewer"

    def test_is_strenum(self):
        assert issubclass(MemberRole, StrEnum)

    def test_members_count(self):
        assert len(MemberRole) == 4


class TestMemberStatus:
    def test_values(self):
        assert MemberStatus.active == "active"
        assert MemberStatus.inactive == "inactive"
        assert MemberStatus.removed == "removed"

    def test_is_strenum(self):
        assert issubclass(MemberStatus, StrEnum)

    def test_members_count(self):
        assert len(MemberStatus) == 3


class TestInviteStatus:
    def test_values(self):
        assert InviteStatus.pending == "pending"
        assert InviteStatus.accepted == "accepted"
        assert InviteStatus.expired == "expired"
        assert InviteStatus.revoked == "revoked"
        assert InviteStatus.cancelled == "cancelled"

    def test_is_strenum(self):
        assert issubclass(InviteStatus, StrEnum)

    def test_members_count(self):
        assert len(InviteStatus) == 5


class TestUserSessionStatus:
    def test_values(self):
        assert UserSessionStatus.active == "active"
        assert UserSessionStatus.expired == "expired"
        assert UserSessionStatus.revoked == "revoked"

    def test_is_strenum(self):
        assert issubclass(UserSessionStatus, StrEnum)

    def test_members_count(self):
        assert len(UserSessionStatus) == 3
