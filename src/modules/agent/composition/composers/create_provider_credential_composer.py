from modules.agent.application.use_cases import CreateProviderCredentialUseCase
from modules.agent.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_provider_credential_controller import CreateProviderCredentialController
from shared.infra.transactional_handler import TransactionalHandler


def create_provider_credential_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = CreateProviderCredentialUseCase(
        credential_repo,
        outbox,
        encryption_key=SETTINGS.encryption_key,
    )
    controller = CreateProviderCredentialController(use_case)
    return TransactionalHandler(uow, controller.handle)
