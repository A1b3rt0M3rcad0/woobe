from uuid import UUID

from modules.agent.application.dtos.skill_dtos import SkillSummary
from modules.agent.application.interfaces.skill_repository import SkillRepository
from modules.agent.application.skill_packages import (
    ImportSkillInput,
    parse_skill_package,
)
from modules.agent.domain.skills import Skill, SkillVersion, skill_package_hash
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError


class SkillCatalog:
    def __init__(self, repository: SkillRepository) -> None:
        self._repository = repository

    async def resolve_development_import(self, project_id, data, skill_id=None):
        package = parse_skill_package(data)
        digest = skill_package_hash(package)
        if skill_id is None:
            # New namespace/import preserves the established portable bootstrap
            # proof. Changed author content receives an immutable dev version.
            try:
                return await self.resolve_import(project_id, data)
            except ConflictError:
                variant = data.model_copy(update={"version": "0.0.0-dev." + digest[:48]})
                return await self.resolve_import(project_id, variant)
        skill = await self._repository.get_skill(project_id, skill_id)
        if skill is None:
            raise NotFoundError("Skill was not found in this Project")
        if skill.name != package["name"]:
            raise ValidationError(
                "Changing a bound Skill name requires an explicit clone"
            )
        versions, offset = [], 0
        while True:
            page = await self._repository.list_versions(
                project_id, skill_id, offset=offset, limit=100
            )
            versions.extend(page)
            if len(page) < 100:
                break
            offset += 100
        version = data.version
        current = next((item for item in versions if item.version == version), None)
        if current is not None and (
            current.package_hash != digest or current.package != package
        ):
            version = "0.0.0-dev." + digest[:48]
            current = next((item for item in versions if item.version == version), None)
        if current is not None:
            if current.package_hash != digest or current.package != package:
                raise ConflictError("Development Skill version has conflicting content")
            return current, False
        return await self.add_version(
            project_id, skill_id, data.model_copy(update={"version": version})
        ), True

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

    async def resolve_import(
        self, project_id: UUID, data: ImportSkillInput
    ) -> tuple[SkillVersion, bool]:
        """Reuse a complete immutable native package, never a coincidental name."""
        package = parse_skill_package(data)
        digest = skill_package_hash(package)
        offset = 0
        while True:
            page = await self._repository.list_skills(
                project_id, query=package["name"], offset=offset, limit=100
            )
            for summary in page:
                if summary.skill.name != package["name"]:
                    continue
                version_offset = 0
                while True:
                    versions = await self._repository.list_versions(
                        project_id, summary.skill.id, offset=version_offset, limit=100
                    )
                    for version in versions:
                        if version.version == data.version:
                            if (
                                version.package_hash == digest
                                and version.package == package
                            ):
                                return version, False
                            raise ConflictError(
                                "Imported Skill version differs from its installed immutable package"
                            )
                    if len(versions) < 100:
                        break
                    version_offset += 100
                return await self.add_version(project_id, summary.skill.id, data), True
            if len(page) < 100:
                break
            offset += 100
        return await self.create(project_id, data), True

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
