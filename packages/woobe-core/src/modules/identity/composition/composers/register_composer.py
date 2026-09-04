from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.identity.infra.database.repositories import SQLAlchemyUserRepository
from modules.identity.infra.database.repositories import SQLAlchemyWorkspaceMemberRepository
from modules.identity.infra.database.repositories import SQLAlchemyWorkspaceRepository
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import RegisterUseCase
from modules.identity.presentation.controllers.register_controller import RegisterController
from shared.infra.transactional_handler import TransactionalHandler


def register_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    use_case = RegisterUseCase(SQLAlchemyUserRepository(uow), SQLAlchemyWorkspaceRepository(uow), SQLAlchemyWorkspaceMemberRepository(uow), SQLAlchemyOutboxEventWriter(uow))
    controller = RegisterController(use_case)
    return TransactionalHandler(uow, controller.handle)
