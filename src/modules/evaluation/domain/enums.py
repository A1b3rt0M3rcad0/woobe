from enum import StrEnum


class EvaluationTargetType(StrEnum):
    AGENT = "agent"
    NETWORK = "network"


class EvaluationSourceType(StrEnum):
    DRAFT = "draft"
    STAGING = "staging"
    RELEASE = "release"


class EvaluationMode(StrEnum):
    ABSOLUTE = "absolute"
    COMPARISON = "comparison"


class EvaluationRunStatus(StrEnum):
    QUEUED = "queued"
    SNAPSHOTTING = "snapshotting"
    EXECUTING = "executing"
    JUDGING = "judging"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class EvaluationTrialStatus(StrEnum):
    PENDING = "pending"
    EXECUTING = "executing"
    WAITING_RUNTIME = "waiting_runtime"
    JUDGING = "judging"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    INCONCLUSIVE = "inconclusive"


class EvaluationTargetSide(StrEnum):
    SINGLE = "single"
    CANDIDATE = "candidate"
    BASELINE = "baseline"


class EvaluationCheckType(StrEnum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"


class EvaluationCheckStatus(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class QualificationStatus(StrEnum):
    QUALIFIED = "qualified"
    QUALIFIED_WITH_WARNINGS = "qualified_with_warnings"
    NOT_QUALIFIED = "not_qualified"
    INCONCLUSIVE = "inconclusive"


class EstimateConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT_DATA = "insufficient_data"
