from modules.identity.application.use_cases import CreateUserUseCase
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
)
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.presentation.controllers.create_user_controller import CreateUserController
from shared.infra.transactional_handler import TransactionalHandler


def create_user_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    user_repo = SQLAlchemyUserRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateUserUseCase(user_repo, outbox)
    controller = CreateUserController(use_case)
    return TransactionalHandler(uow, controller.handle)
