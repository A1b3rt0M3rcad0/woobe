from modules.core.infra.services.api_key_delegation import SqlApiKeyDelegationPolicy
from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.repositories import SQLAlchemyApiKeyRepository
from modules.core.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.core.application.use_cases import RotateApiKeyUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.rotate_api_key_controller import (
    RotateApiKeyController,
)
from shared.infra.transactional_handler import TransactionalHandler


def rotate_api_key_composer() -> TransactionalHandler:
    unit_of_work = CoreUnitOfWork(DATABASE_ENGINE)
    use_case = RotateApiKeyUseCase(
        SQLAlchemyApiKeyRepository(unit_of_work),
        SQLAlchemyOutboxEventWriter(unit_of_work),
        delegation_policy=SqlApiKeyDelegationPolicy(unit_of_work),
    )
    controller = RotateApiKeyController(use_case)
    return TransactionalHandler(unit_of_work, controller.handle)
