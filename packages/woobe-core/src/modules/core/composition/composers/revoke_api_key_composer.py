from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.repositories import SQLAlchemyApiKeyRepository
from modules.core.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.core.application.use_cases import RevokeApiKeyUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.revoke_api_key_controller import RevokeApiKeyController
from shared.infra.transactional_handler import TransactionalHandler


def revoke_api_key_composer() -> TransactionalHandler:
    unit_of_work = CoreUnitOfWork(DATABASE_ENGINE)
    use_case = RevokeApiKeyUseCase(SQLAlchemyApiKeyRepository(unit_of_work), SQLAlchemyOutboxEventWriter(unit_of_work))
    controller = RevokeApiKeyController(use_case)
    return TransactionalHandler(unit_of_work, controller.handle)
