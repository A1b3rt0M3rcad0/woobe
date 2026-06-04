from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.repositories import (
    SQLAlchemyOrganizationInviteRepository,
    SQLAlchemyOrganizationRepository,
    SQLAlchemyOutboxEventWriter,
)
from modules.identity.service.use_cases import InviteUserUseCase
from modules.identity.presentation.controllers.create_invite_controller import CreateInviteController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_invite_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    org_repo = SQLAlchemyOrganizationRepository(uow)
    invite_repo = SQLAlchemyOrganizationInviteRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = InviteUserUseCase(org_repo, invite_repo, outbox)
    controller = CreateInviteController(use_case)
    return TransactionalHandler(uow, controller.handle)
