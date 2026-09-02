from modules.core.application.use_cases import RevokeApiKeyUseCase
from modules.core.infra.database.repositories import (
    SQLAlchemyApiKeyRepository,
    SQLAlchemyOutboxEventWriter,
)
from modules.core.presentation.controllers.revoke_api_key_controller import (
    RevokeApiKeyController,
)

from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def revoke_api_key_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyApiKeyRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = RevokeApiKeyUseCase(repository, outbox)
    controller = RevokeApiKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)
