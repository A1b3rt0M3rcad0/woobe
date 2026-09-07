from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from modules.agent.application.interfaces.skill_repository import SkillRepository
from modules.agent.domain.skills import Skill, SkillVersion
from modules.agent.infra.database.skill_models import SkillModel, SkillVersionModel
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.contracts.errors import ConflictError


def _skill(model: SkillModel) -> Skill:
    return Skill(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        created_at=model.created_at,
    )


def _version(model: SkillVersionModel, project_id: UUID) -> SkillVersion:
    return SkillVersion(
        id=model.id,
        skill_id=model.skill_id,
        project_id=project_id,
        version=model.version,
        package=model.package,
        package_hash=model.package_hash,
        created_at=model.created_at,
    )


class SQLAlchemySkillRepository(SkillRepository):
    def __init__(self, uow: AgentUnitOfWork) -> None:
        self._uow = uow

    async def list_skills(
        self, project_id: UUID, *, query: str = "", offset: int = 0, limit: int = 50
    ) -> list[Skill]:
        statement = select(SkillModel).where(SkillModel.project_id == project_id)
        if query:
            statement = statement.where(
                SkillModel.name.icontains(query, autoescape=True)
            )
        result = await self._uow.session.scalars(
            statement.order_by(SkillModel.name, SkillModel.id)
            .offset(offset)
            .limit(limit)
        )
        return [_skill(item) for item in result]

    async def get_skill(self, project_id: UUID, skill_id: UUID) -> Skill | None:
        result = await self._uow.session.scalar(
            select(SkillModel).where(
                SkillModel.id == skill_id, SkillModel.project_id == project_id
            )
        )
        return _skill(result) if result is not None else None

    async def create_skill(self, skill: Skill) -> Skill:
        model = SkillModel(id=skill.id, project_id=skill.project_id, name=skill.name)
        self._uow.session.add(model)
        try:
            await self._uow.session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "A Skill with this name already exists in the Project"
            ) from exc
        return _skill(model)

    async def list_versions(
        self, project_id: UUID, skill_id: UUID, *, offset: int = 0, limit: int = 50
    ) -> list[SkillVersion]:
        statement = (
            select(SkillVersionModel)
            .join(SkillModel)
            .where(
                SkillModel.project_id == project_id,
                SkillVersionModel.skill_id == skill_id,
            )
            .order_by(SkillVersionModel.created_at.desc(), SkillVersionModel.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._uow.session.scalars(statement)
        return [_version(item, project_id) for item in result]

    async def get_version(
        self, project_id: UUID, version_id: UUID
    ) -> SkillVersion | None:
        result = await self._uow.session.scalar(
            select(SkillVersionModel)
            .join(SkillModel)
            .where(
                SkillModel.project_id == project_id,
                SkillVersionModel.id == version_id,
            )
        )
        return _version(result, project_id) if result is not None else None

    async def create_version(self, version: SkillVersion) -> SkillVersion:
        model = SkillVersionModel(
            id=version.id,
            skill_id=version.skill_id,
            version=version.version,
            package=version.package,
            package_hash=version.package_hash,
        )
        self._uow.session.add(model)
        try:
            await self._uow.session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "This Skill version already exists; publish a new version"
            ) from exc
        return _version(model, version.project_id)
