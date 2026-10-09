"""Internal exact-snapshot admission; transport metadata cannot grant it."""
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CandidateExecutionGrant:
    project_id: UUID
    agent_id: UUID
    snapshot_id: UUID
    evaluation_id: UUID
    run_id: UUID | None = None
    runtime_digest: str | None = None
    record_digest: str | None = None
    binding_digest: str | None = None


candidate_execution: ContextVar[CandidateExecutionGrant | None] = ContextVar(
    "candidate_execution", default=None
)
