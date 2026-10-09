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


class ASaCOperationColumns:
    project_id: Mapped[UUID]
    resource_id: Mapped[UUID]
    actor: Mapped[str] = mapped_column(String(96))
    operation_id: Mapped[UUID]
    request_digest: Mapped[str] = mapped_column(String(71))
    result: Mapped[dict] = mapped_column(JSON)
