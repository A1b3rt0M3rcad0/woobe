from modules.identity.application.use_cases import RegisterUseCase
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
    SQLAlchemyWorkspaceMemberRepository,
    SQLAlchemyWorkspaceRepository,
)
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.presentation.controllers.register_controller import RegisterController
from shared.infra.transactional_handler import TransactionalHandler


def register_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    user_repo = SQLAlchemyUserRepository(uow)
    workspace_repo = SQLAlchemyWorkspaceRepository(uow)
    member_repo = SQLAlchemyWorkspaceMemberRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = RegisterUseCase(user_repo, workspace_repo, member_repo, outbox)
    controller = RegisterController(use_case)
    return TransactionalHandler(uow, controller.handle)
