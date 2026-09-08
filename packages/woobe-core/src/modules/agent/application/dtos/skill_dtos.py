from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from modules.agent.domain.skills import Skill, SkillVersion


@dataclass(frozen=True, slots=True)
class SkillSummary:
    skill: Skill
    latest_version: SkillVersion | None
    version_count: int


class ImportSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?$",
    )
    skill_md: str = Field(min_length=1, max_length=200_000)
    resources: dict[str, str] = Field(default_factory=dict, max_length=64)
    required_tools: list[str] = Field(default_factory=list, max_length=64)


class SkillListQuery(BaseModel):
    query: str = Field(default="", max_length=200)
    offset: int = Field(default=0, ge=0, le=1_000_000)
    limit: int = Field(default=50, ge=1, le=100)
