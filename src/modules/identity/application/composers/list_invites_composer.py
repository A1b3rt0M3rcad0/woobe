from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.repositories import SQLAlchemyOrganizationInviteRepository
from modules.identity.service.use_cases import ListInvitesUseCase
from modules.identity.presentation.controllers.list_invites_controller import ListInvitesController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_invites_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    invite_repo = SQLAlchemyOrganizationInviteRepository(uow)
    use_case = ListInvitesUseCase(invite_repo)
    controller = ListInvitesController(use_case)
    return TransactionalHandler(uow, controller.handle)
