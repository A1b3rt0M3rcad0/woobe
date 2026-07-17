from enum import StrEnum


class NetworkEnvironment(StrEnum):
    DRAFT = "draft"
    STAGING = "staging"
    PRODUCTION = "production"


class NetworkVersionKind(StrEnum):
    STAGING = "staging"
    RELEASE = "release"


class NetworkSessionStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class NetworkExecutionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    UNCERTAIN = "uncertain"


class NetworkInvocationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NetworkEventType(StrEnum):
    EXECUTION_ACCEPTED = "execution_accepted"
    EXECUTION_QUEUED = "execution_queued"
    EXECUTION_STARTED = "execution_started"
    INVOCATION_STARTED = "agent_invocation_started"
    INVOCATION_FAILED = "agent_invocation_failed"
    AGENT_ACTIVITY = "agent_activity"
    DELEGATION_STARTED = "delegation_started"
    DELEGATION_COMPLETED = "delegation_completed"
    TOKEN = "token"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    HEARTBEAT = "heartbeat"
