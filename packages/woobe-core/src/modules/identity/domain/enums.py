from enum import StrEnum, auto


class UserStatus(StrEnum):
    active = auto()
    inactive = auto()
    suspended = auto()
    deleted = auto()


class WorkspaceStatus(StrEnum):
    active = auto()
    inactive = auto()
    suspended = auto()


class MemberRole(StrEnum):
    owner = auto()
    admin = auto()
    member = auto()
    viewer = auto()


class MemberStatus(StrEnum):
    active = auto()
    inactive = auto()
    removed = auto()


class InviteStatus(StrEnum):
    pending = auto()
    accepted = auto()
    expired = auto()
    revoked = auto()
    cancelled = auto()


class UserSessionStatus(StrEnum):
    active = auto()
    expired = auto()
    revoked = auto()
