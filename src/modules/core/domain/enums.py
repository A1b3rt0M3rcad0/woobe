from enum import StrEnum, auto


class ProjectStatus(StrEnum):
    active = auto()
    archived = auto()
    deleted = auto()


class ApiKeyStatus(StrEnum):
    active = auto()
    revoked = auto()
    expired = auto()


class ApiKeyScope(StrEnum):
    reading = auto()
    writing = auto()
    admin = auto()
    custom = auto()
