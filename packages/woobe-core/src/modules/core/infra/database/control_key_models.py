from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    LargeBinary,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel

_JSON = JSON().with_variant(JSONB(), "postgresql")


class WorkspaceControlKeyModel(BaseModel):
    __tablename__ = "workspace_control_keys"
    __table_args__ = (
        UniqueConstraint("key_hash", name="uq_core_workspace_control_keys_key_hash"),
        ForeignKeyConstraint(
            ["workspace_category_id", "workspace_category_revision"],
            [
                "identity.authority_category_versions.category_id",
                "identity.authority_category_versions.revision",
            ],
            name="fk_core_control_key_workspace_category",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_core_workspace_control_keys_prefix_version", "key_prefix", "key_version"
        ),
        Index(
            "ix_core_workspace_control_keys_workspace_status", "workspace_id", "status"
        ),
        Index(
            "ix_core_workspace_control_keys_credential_created",
            "credential_id",
            "created_at",
        ),
        {"schema": "core"},
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity.workspaces.id", ondelete="CASCADE")
    )
    credential_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    key_prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(SmallInteger, server_default="2")
    permissions: Mapped[list[str]] = mapped_column(
        _JSON, server_default=text("'[]'::jsonb")
    )
    status: Mapped[str] = mapped_column(String(32), server_default="active")
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delegation_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revision: Mapped[int] = mapped_column(Integer, server_default="1")
    on_project_create_permissions: Mapped[list[str]] = mapped_column(
        _JSON, server_default=text("'[]'::jsonb")
    )
    workspace_category_id: Mapped[UUID | None] = mapped_column(nullable=True)
    workspace_category_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_by_control_key_id: Mapped[UUID | None] = mapped_column(nullable=True)
    rotated_from_id: Mapped[UUID | None] = mapped_column(nullable=True)


class ControlKeyProjectGrantModel(BaseModel):
    __tablename__ = "workspace_control_key_project_grants"
    __table_args__ = (
        UniqueConstraint(
            "control_key_id", "project_id", name="uq_core_control_key_project_grant"
        ),
        ForeignKeyConstraint(
            ["category_id", "category_revision"],
            [
                "identity.authority_category_versions.category_id",
                "identity.authority_category_versions.revision",
            ],
            name="fk_core_control_key_project_category",
            ondelete="RESTRICT",
        ),
        Index("ix_core_control_key_grants_project", "project_id", "control_key_id"),
        {"schema": "core"},
    )
    control_key_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "core.workspace_control_keys.id",
            name="fk_core_control_key_grants_key_id",
            ondelete="CASCADE",
        )
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "core.projects.id",
            name="fk_core_control_key_grants_project_id",
            ondelete="CASCADE",
        )
    )
    permissions: Mapped[list[str]] = mapped_column(
        _JSON, server_default=text("'[]'::jsonb")
    )
    conditions: Mapped[dict[str, Any]] = mapped_column(
        _JSON, server_default=text("'{}'::jsonb")
    )
    category_id: Mapped[UUID | None] = mapped_column(nullable=True)
    category_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
