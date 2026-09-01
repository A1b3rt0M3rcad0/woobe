from modules.agent.application.use_cases import UpdateProviderCredentialUseCase
from modules.agent.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.update_provider_credential_controller import UpdateProviderCredentialController
from shared.infra.transactional_handler import TransactionalHandler


def update_provider_credential_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = UpdateProviderCredentialUseCase(
        credential_repo,
        outbox,
        encryption_key=SETTINGS.encryption_key,
    )
    controller = UpdateProviderCredentialController(use_case)
    return TransactionalHandler(uow, controller.handle)
