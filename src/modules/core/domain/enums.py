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


PROJECT_API_KEY_SCOPES = frozenset(
    {
        "runtime:execute",
        "traces:read",
        "usage:read",
    }
)
PROJECT_API_KEY_ACCEPTED_SCOPES = PROJECT_API_KEY_SCOPES | frozenset(
    scope.value for scope in ApiKeyScope
)
