"""Persistence mixins instantiated by Agent and Network, never shared owners."""
from uuid import UUID
from sqlalchemy import Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column


class ASaCDraftColumns:
    project_id: Mapped[UUID]
    resource_id: Mapped[UUID]
    resource_uid: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(80))
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_id: Mapped[UUID | None] = mapped_column(nullable=True)
    definition_digest: Mapped[str | None] = mapped_column(String(71), nullable=True)
    origin: Mapped[dict] = mapped_column(JSON)
    working_revision_id: Mapped[str | None] = mapped_column(String(39), nullable=True)


class ASaCRevisionColumns:
    project_id: Mapped[UUID]
    resource_id: Mapped[UUID]
    resource_uid: Mapped[UUID]
    revision_id: Mapped[str] = mapped_column(String(39))
    artifact_id: Mapped[UUID]
    author_artifact_id: Mapped[UUID | None] = mapped_column(nullable=True)
    document: Mapped[dict] = mapped_column(JSON)
    actor: Mapped[str] = mapped_column(String(96))
    component_uids: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provider_uids: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ASaCCandidateColumns:
    project_id: Mapped[UUID]
    resource_id: Mapped[UUID]
    resource_uid: Mapped[UUID]
    actor: Mapped[str] = mapped_column(String(96))
    operation_id: Mapped[UUID]
    request_digest: Mapped[str] = mapped_column(String(71))
    revision_id: Mapped[str] = mapped_column(String(39))
    record_digest: Mapped[str] = mapped_column(String(71))
    artifact_id: Mapped[UUID]
    draft_id: Mapped[UUID]
    draft_generation: Mapped[int] = mapped_column(Integer)
    preparation_operation_id: Mapped[UUID]
    state: Mapped[str] = mapped_column(String(16), default="preparing")
    root_snapshot_id: Mapped[UUID | None] = mapped_column(nullable=True)
    snapshot_ids: Mapped[dict] = mapped_column(JSON)
    native_bindings: Mapped[dict] = mapped_column(JSON, default=dict)
    runtime_digest: Mapped[str | None] = mapped_column(String(71), nullable=True)
    runtime_fingerprints: Mapped[dict] = mapped_column(JSON, default=dict)
    runtime_digest_scope: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ASaCOperationColumns:
    project_id: Mapped[UUID]
    resource_id: Mapped[UUID]
    actor: Mapped[str] = mapped_column(String(96))
    operation_id: Mapped[UUID]
    request_digest: Mapped[str] = mapped_column(String(71))
    result: Mapped[dict] = mapped_column(JSON)


class ASaCEvaluationColumns:
    project_id: Mapped[UUID]
    resource_id: Mapped[UUID]
    candidate_id: Mapped[UUID]
    actor: Mapped[str] = mapped_column(String(96))
    operation_id: Mapped[UUID]
    request_digest: Mapped[str] = mapped_column(String(71))
    state: Mapped[str] = mapped_column(String(16))
    suite: Mapped[dict] = mapped_column(JSON)
    suite_digest: Mapped[str] = mapped_column(String(71))
    dataset_digest: Mapped[str] = mapped_column(String(71))
    policy_digest: Mapped[str] = mapped_column(String(71))
    runtime_digest: Mapped[str] = mapped_column(String(71))
    record_digest: Mapped[str] = mapped_column(String(71))
    binding_digest: Mapped[str] = mapped_column(String(71))
    cases: Mapped[list] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ASaCPublicationColumns:
    project_id: Mapped[UUID]
    resource_id: Mapped[UUID]
    resource_uid: Mapped[UUID]
    candidate_id: Mapped[UUID]
    evaluation_id: Mapped[UUID]
    release_id: Mapped[UUID]
    release_version: Mapped[str] = mapped_column(String(64))
    revision_id: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(96))
    operation_id: Mapped[UUID]
    request_digest: Mapped[str] = mapped_column(String(71))
    reused: Mapped[bool]
    reason: Mapped[str] = mapped_column(String(2048))
    evidence: Mapped[dict] = mapped_column(JSON)
