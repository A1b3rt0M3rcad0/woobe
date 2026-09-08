from uuid import UUID

from modules.agent.application.dtos.skill_dtos import SkillSummary
from modules.agent.application.interfaces.skill_repository import SkillRepository
from modules.agent.application.skill_packages import (
    ImportSkillInput,
    parse_skill_package,
)
from modules.agent.domain.skills import Skill, SkillVersion, skill_package_hash
from shared.contracts.errors import NotFoundError, ValidationError


class SkillCatalog:
    def __init__(self, repository: SkillRepository) -> None:
        self._repository = repository

    async def create(self, project_id: UUID, data: ImportSkillInput) -> SkillVersion:
        package = parse_skill_package(data)
        skill = await self._repository.create_skill(
            Skill(project_id=project_id, name=package["name"])
        )
        return await self._repository.create_version(
            SkillVersion(
                skill_id=skill.id,
                project_id=project_id,
                version=data.version,
                package=package,
                package_hash=skill_package_hash(package),
            )
        )

    async def add_version(
        self, project_id: UUID, skill_id: UUID, data: ImportSkillInput
    ) -> SkillVersion:
        skill = await self._repository.get_skill(project_id, skill_id)
        if skill is None:
            raise NotFoundError("Skill was not found in this Project")
        package = parse_skill_package(data)
        if package["name"] != skill.name:
            raise ValidationError("A new Skill version must preserve its name")
        return await self._repository.create_version(
            SkillVersion(
                skill_id=skill.id,
                project_id=project_id,
                version=data.version,
                package=package,
                package_hash=skill_package_hash(package),
            )
        )

    async def list(
        self, project_id: UUID, *, query: str, offset: int, limit: int
    ) -> list[SkillSummary]:
        return await self._repository.list_skills(
            project_id, query=query, offset=offset, limit=limit
        )

    async def versions(
        self, project_id: UUID, skill_id: UUID, *, offset: int, limit: int
    ) -> list[SkillVersion]:
        if await self._repository.get_skill(project_id, skill_id) is None:
            raise NotFoundError("Skill was not found in this Project")
        return await self._repository.list_versions(
            project_id, skill_id, offset=offset, limit=limit
        )

    async def get_version(self, project_id: UUID, version_id: UUID) -> SkillVersion:
        version = await self._repository.get_version(project_id, version_id)
        if version is None:
            raise NotFoundError("Skill version was not found in this Project")
        return version
