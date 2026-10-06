from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel

_JSON = JSON().with_variant(JSONB(), "postgresql")


class AuthorityCategoryModel(BaseModel):
    __tablename__ = "authority_categories"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "scope", "name", name="uq_identity_authority_category_name"
        ),
        CheckConstraint(
            "scope IN ('workspace', 'project')",
            name="ck_identity_authority_category_scope",
        ),
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_identity_authority_category_status",
        ),
        CheckConstraint("revision > 0", name="ck_identity_authority_category_revision"),
        {"schema": "identity"},
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity.workspaces.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scope: Mapped[str] = mapped_column(String(16))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="active")
    system: Mapped[bool] = mapped_column(Boolean, default=False)


class AuthorityCategoryVersionModel(BaseModel):
    __tablename__ = "authority_category_versions"
    __table_args__ = (
        UniqueConstraint(
            "category_id", "revision", name="uq_identity_authority_category_version"
        ),
        CheckConstraint("revision > 0", name="ck_identity_authority_version_revision"),
        {"schema": "identity"},
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity.authority_categories.id", ondelete="CASCADE")
    )
    revision: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(128))
    permissions: Mapped[list[str]] = mapped_column(_JSON, default=list)
    conditions: Mapped[dict[str, Any]] = mapped_column(_JSON, default=dict)
    catalog_revision: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_by_control_key_id: Mapped[UUID | None] = mapped_column(nullable=True)


class AuthorityAssignmentModel(BaseModel):
    __tablename__ = "authority_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["category_id", "category_revision"],
            [
                "identity.authority_category_versions.category_id",
                "identity.authority_category_versions.revision",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "workspace_id",
            "subject_user_id",
            "scope_id",
            name="uq_identity_authority_assignment_scope",
        ),
        Index(
            "ix_identity_authority_assignment_actor",
            "workspace_id",
            "subject_user_id",
            "status",
        ),
        {"schema": "identity"},
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity.workspaces.id", ondelete="CASCADE")
    )
    subject_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity.users.id", ondelete="CASCADE")
    )
    # Workspace id for a workspace assignment; Project id otherwise.
    scope_id: Mapped[UUID]
    project_id: Mapped[UUID | None] = mapped_column(nullable=True)
    category_id: Mapped[UUID]
    category_revision: Mapped[int] = mapped_column(Integer)
    permissions: Mapped[list[str]] = mapped_column(_JSON, default=list)
    conditions: Mapped[dict[str, Any]] = mapped_column(_JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="active")
    revision: Mapped[int] = mapped_column(Integer, default=1)


class AuthorityAuditModel(BaseModel):
    __tablename__ = "authority_audit"
    __table_args__ = (
        Index("ix_identity_authority_audit_workspace", "workspace_id", "id"),
        {"schema": "identity"},
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity.workspaces.id", ondelete="CASCADE")
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    actor_control_key_id: Mapped[UUID | None] = mapped_column(nullable=True)
    operation: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[UUID]
    revision: Mapped[int] = mapped_column(Integer)
    details: Mapped[dict[str, Any]] = mapped_column(_JSON, default=dict)
