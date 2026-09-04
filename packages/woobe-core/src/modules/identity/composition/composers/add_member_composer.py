from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.identity.infra.database.repositories import SQLAlchemyUserRepository
from modules.identity.infra.database.repositories import SQLAlchemyWorkspaceMemberRepository
from modules.identity.infra.database.repositories import SQLAlchemyWorkspaceRepository
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import AddMemberToWorkspaceUseCase
from modules.identity.presentation.controllers.add_member_controller import AddMemberController
from shared.infra.transactional_handler import TransactionalHandler


def add_member_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    use_case = AddMemberToWorkspaceUseCase(SQLAlchemyWorkspaceRepository(uow), SQLAlchemyUserRepository(uow), SQLAlchemyWorkspaceMemberRepository(uow), SQLAlchemyOutboxEventWriter(uow))
    controller = AddMemberController(use_case)
    return TransactionalHandler(uow, controller.handle)
