from enum import StrEnum, auto


class ProjectStatus(StrEnum):
    active = auto()
    archived = auto()
    deleted = auto()


class ApiKeyStatus(StrEnum):
    active = auto()
    revoked = auto()
    expired = auto()


class ApiKeyKind(StrEnum):
    project = auto()
    runtime = auto()
    chat_surface = auto()


class RuntimeTargetType(StrEnum):
    agent = auto()
    network = auto()


class RuntimeEnvironment(StrEnum):
    staging = auto()
    production = auto()


class RuntimeInterface(StrEnum):
    http = auto()
    stream = auto()
    jobs = auto()


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

RUNTIME_INTERFACES = frozenset(interface.value for interface in RuntimeInterface)
