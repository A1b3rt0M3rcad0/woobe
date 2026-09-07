from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel


class SkillModel(BaseModel):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_agent_skills_project_name"),
        {"schema": "agent"},
    )
    project_id: Mapped[UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(64))


class SkillVersionModel(BaseModel):
    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_id", "version", name="uq_agent_skill_versions_version"),
        Index("ix_agent_skill_versions_skill_created", "skill_id", "created_at"),
        {"schema": "agent"},
    )
    skill_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent.skills.id", ondelete="CASCADE")
    )
    version: Mapped[str] = mapped_column(String(64))
    package: Mapped[dict[str, Any]] = mapped_column(JSONB)
    package_hash: Mapped[str] = mapped_column(String(64))
