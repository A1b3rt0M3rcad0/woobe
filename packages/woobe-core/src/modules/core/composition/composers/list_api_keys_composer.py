from modules.core.application.use_cases import ListApiKeysByProjectUseCase
from modules.core.infra.database.repositories import SQLAlchemyApiKeyRepository
from modules.core.infra.security.api_key_issuer import SharedApiKeyIssuer
from modules.core.presentation.controllers.list_api_keys_controller import (
    ListApiKeysController,
)

from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def list_api_keys_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyApiKeyRepository(uow)
    api_key_issuer = SharedApiKeyIssuer()
    use_case = ListApiKeysByProjectUseCase(repository, api_key_issuer)
    controller = ListApiKeysController(use_case)
    return TransactionalHandler(uow, controller.handle)
