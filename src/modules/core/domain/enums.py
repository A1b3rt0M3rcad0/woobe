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
    runtime_execute = "runtime:execute"
    traces_read = "traces:read"
    usage_read = "usage:read"

    # Legacy values remain parseable for existing rows but are not accepted
    # for newly issued project API keys.
    reading = auto()
    writing = auto()
    admin = auto()
    custom = auto()


PROJECT_API_KEY_SCOPES = frozenset(
    {
        ApiKeyScope.runtime_execute.value,
        ApiKeyScope.traces_read.value,
        ApiKeyScope.usage_read.value,
    }
)
