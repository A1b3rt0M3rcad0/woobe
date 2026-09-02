from modules.identity.application.use_cases import ListInvitesUseCase
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import SQLAlchemyWorkspaceInviteRepository
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.presentation.controllers.list_invites_controller import (
    ListInvitesController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_invites_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    invite_repo = SQLAlchemyWorkspaceInviteRepository(uow)
    use_case = ListInvitesUseCase(invite_repo)
    controller = ListInvitesController(use_case)
    return TransactionalHandler(uow, controller.handle)
