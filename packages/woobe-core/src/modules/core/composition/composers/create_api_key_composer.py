from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.repositories import SQLAlchemyApiKeyRepository
from modules.core.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.core.infra.database.repositories import SQLAlchemyProjectRepository
from modules.core.application.use_cases import CreateApiKeyUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.create_api_key_controller import CreateApiKeyController
from shared.infra.transactional_handler import TransactionalHandler


def create_api_key_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    use_case = CreateApiKeyUseCase(SQLAlchemyProjectRepository(uow), SQLAlchemyApiKeyRepository(uow), SQLAlchemyOutboxEventWriter(uow))
    controller = CreateApiKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)
