from modules.identity.application.use_cases import InviteUserUseCase
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyWorkspaceInviteRepository,
    SQLAlchemyWorkspaceRepository,
)
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.presentation.controllers.create_invite_controller import CreateInviteController
from shared.infra.transactional_handler import TransactionalHandler


def create_invite_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    use_case = InviteUserUseCase(
        SQLAlchemyWorkspaceRepository(uow),
        SQLAlchemyWorkspaceInviteRepository(uow),
        SQLAlchemyOutboxEventWriter(uow),
    )
    controller = CreateInviteController(use_case)
    return TransactionalHandler(uow, controller.handle)
