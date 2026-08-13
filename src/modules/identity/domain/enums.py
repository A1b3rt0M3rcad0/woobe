from enum import StrEnum, auto


class UserStatus(StrEnum):
    active = auto()
    inactive = auto()
    suspended = auto()
    deleted = auto()


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
