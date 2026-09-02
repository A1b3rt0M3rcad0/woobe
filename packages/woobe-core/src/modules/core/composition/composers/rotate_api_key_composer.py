from modules.core.application.use_cases import RotateApiKeyUseCase
from modules.core.infra.database.repositories import (
    SQLAlchemyApiKeyRepository,
    SQLAlchemyOutboxEventWriter,
)
from modules.core.infra.security.api_key_issuer import SharedApiKeyIssuer
from modules.core.presentation.controllers.rotate_api_key_controller import (
    RotateApiKeyController,
)

from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def rotate_api_key_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyApiKeyRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    api_key_issuer = SharedApiKeyIssuer()
    use_case = RotateApiKeyUseCase(repository, outbox, api_key_issuer)
    controller = RotateApiKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)
