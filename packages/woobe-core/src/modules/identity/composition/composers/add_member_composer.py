from modules.identity.application.use_cases import AddMemberToWorkspaceUseCase
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
    SQLAlchemyWorkspaceMemberRepository,
    SQLAlchemyWorkspaceRepository,
)
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.presentation.controllers.add_member_controller import AddMemberController
from shared.infra.transactional_handler import TransactionalHandler


def add_member_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    workspace_repo = SQLAlchemyWorkspaceRepository(uow)
    user_repo = SQLAlchemyUserRepository(uow)
    member_repo = SQLAlchemyWorkspaceMemberRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = AddMemberToWorkspaceUseCase(
        workspace_repo,
        user_repo,
        member_repo,
        outbox,
    )
    controller = AddMemberController(use_case)
    return TransactionalHandler(uow, controller.handle)
