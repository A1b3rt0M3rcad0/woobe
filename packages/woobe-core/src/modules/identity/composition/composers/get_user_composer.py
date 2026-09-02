from modules.identity.application.use_cases import GetUserUseCase
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import SQLAlchemyUserRepository
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.presentation.controllers.get_user_controller import GetUserController
from shared.infra.transactional_handler import TransactionalHandler


def get_user_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    user_repo = SQLAlchemyUserRepository(uow)
    use_case = GetUserUseCase(user_repo)
    controller = GetUserController(use_case)
    return TransactionalHandler(uow, controller.handle)
