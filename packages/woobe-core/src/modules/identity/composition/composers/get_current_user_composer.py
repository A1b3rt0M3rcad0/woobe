from modules.identity.application.use_cases import GetCurrentUserUseCase
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.presentation.controllers.get_current_user_controller import (
    GetCurrentUserController,
)
from shared.infra.transactional_handler import TransactionalHandler


def get_current_user_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    use_case = GetCurrentUserUseCase()
    controller = GetCurrentUserController(use_case)
    return TransactionalHandler(uow, controller.handle)
