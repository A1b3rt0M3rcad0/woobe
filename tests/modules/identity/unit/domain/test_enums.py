from modules.identity.domain.enums import (
    InviteStatus,
    MemberRole,
    MemberStatus,
    WorkspaceStatus,
    UserSessionStatus,
    UserStatus,
)


class TestUserStatus:
    def test_active_is_default(self):
        assert UserStatus.active.value == "active"

    def test_all_values(self):
        values = {s.value for s in UserStatus}
        assert values == {"active", "inactive", "suspended", "deleted"}


class TestWorkspaceStatus:
    def test_all_values(self):
        values = {s.value for s in WorkspaceStatus}
        assert values == {"active", "inactive", "suspended"}


class TestMemberRole:
    def test_all_values(self):
        values = {s.value for s in MemberRole}
        assert values == {"owner", "admin", "member", "viewer"}


class TestMemberStatus:
    def test_all_values(self):
        values = {s.value for s in MemberStatus}
        assert values == {"active", "inactive", "removed"}


class TestInviteStatus:
    def test_all_values(self):
        values = {s.value for s in InviteStatus}
        assert values == {"pending", "accepted", "expired", "revoked", "cancelled"}


class TestUserSessionStatus:
    def test_all_values(self):
        values = {s.value for s in UserSessionStatus}
        assert values == {"active", "expired", "revoked"}
