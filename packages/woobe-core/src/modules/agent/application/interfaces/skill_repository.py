from typing import Protocol
from uuid import UUID

from modules.agent.application.dtos.skill_dtos import SkillSummary
from modules.agent.domain.skills import Skill, SkillVersion


class SkillRepository(Protocol):
    async def list_skills(
        self, project_id: UUID, *, query: str, offset: int, limit: int
    ) -> list[SkillSummary]: ...
    async def get_skill(self, project_id: UUID, skill_id: UUID) -> Skill | None: ...
    async def create_skill(self, skill: Skill) -> Skill: ...
    async def list_versions(
        self, project_id: UUID, skill_id: UUID, *, offset: int, limit: int
    ) -> list[SkillVersion]: ...
    async def get_version(
        self, project_id: UUID, version_id: UUID
    ) -> SkillVersion | None: ...
    async def create_version(self, version: SkillVersion) -> SkillVersion: ...
