from typing import Literal

from modules.agent.application.use_cases.skill_cases import SkillCatalog
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.skill_repository import SQLAlchemySkillRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.skill_catalog_controller import (
    SkillCatalogController,
)
from shared.infra.transactional_handler import TransactionalHandler


def skill_catalog_composer(
    operation: Literal["list", "create", "versions", "add_version", "get_version"],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    if operation in {"list", "versions", "get_version"}:
        uow.mark_read_only()
    controller = SkillCatalogController(
        SkillCatalog(SQLAlchemySkillRepository(uow)), operation
    )
    return TransactionalHandler(uow, controller.handle)
