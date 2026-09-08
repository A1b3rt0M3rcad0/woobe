from __future__ import annotations

from typing import Protocol
from uuid import UUID

from modules.agent.application.dtos.skill_dtos import ImportSkillInput, SkillSummary
from modules.agent.domain.skills import SkillVersion


class SkillCatalogOperations(Protocol):
    async def create(self, project_id: UUID, data: ImportSkillInput) -> SkillVersion: ...

    async def add_version(
        self,
        project_id: UUID,
        skill_id: UUID,
        data: ImportSkillInput,
    ) -> SkillVersion: ...

    async def list(
        self,
        project_id: UUID,
        *,
        query: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> list[SkillSummary]: ...

    async def versions(
        self,
        project_id: UUID,
        skill_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[SkillVersion]: ...

    async def get_version(
        self,
        project_id: UUID,
        version_id: UUID,
    ) -> SkillVersion: ...
