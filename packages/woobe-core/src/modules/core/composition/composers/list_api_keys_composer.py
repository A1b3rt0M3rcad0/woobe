from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.repositories import SQLAlchemyApiKeyRepository
from modules.core.application.use_cases import ListApiKeysByProjectUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.list_api_keys_controller import ListApiKeysController
from shared.infra.transactional_handler import TransactionalHandler


def list_api_keys_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    use_case = ListApiKeysByProjectUseCase(SQLAlchemyApiKeyRepository(uow))
    controller = ListApiKeysController(use_case)
    return TransactionalHandler(uow, controller.handle)

