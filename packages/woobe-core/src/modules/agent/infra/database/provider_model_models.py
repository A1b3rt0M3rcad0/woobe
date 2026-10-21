"""Provider Model SQL mapping, independent of repository implementations."""

from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, FetchedValue, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from shared.infra.database.base import BaseModel


class ProviderModelModel(BaseModel):
    __mapper_args__ = {"eager_defaults": True}
    __tablename__ = "provider_models"
    __table_args__ = (
        CheckConstraint("definition_revision >= 1", name="ck_provider_model_definition_revision"),
        UniqueConstraint(
            "project_id",
            "provider_credential_id",
            "model",
            "spec_hash",
            name="uq_provider_models_project_credential_spec",
        ),
        Index("ix_provider_models_project_id", "project_id"),
        Index("ix_provider_models_credential_id", "provider_credential_id"),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    definition_revision: Mapped[int] = mapped_column(
        BigInteger, server_default=text("1"), server_onupdate=FetchedValue()
    )
    provider_credential_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent.provider_credentials.id")
    )
    name: Mapped[str] = mapped_column(String(255))
    model: Mapped[str] = mapped_column(String(255))
    model_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    spec_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spec_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    meta: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
