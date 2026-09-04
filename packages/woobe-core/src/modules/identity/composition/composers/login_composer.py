from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import SQLAlchemyUserRepository
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import LoginUseCase
from modules.identity.presentation.controllers.login_controller import LoginController
from shared.infra.transactional_handler import TransactionalHandler


def login_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    use_case = LoginUseCase(SQLAlchemyUserRepository(uow))
    controller = LoginController(use_case)
    return TransactionalHandler(uow, controller.handle)

