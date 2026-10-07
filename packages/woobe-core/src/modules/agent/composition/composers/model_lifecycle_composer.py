from modules.agent.composition.factories.provider_dependency_reader_factory import build_provider_dependency_reader
from modules.agent.application.use_cases.provider_management_cases import (
    ArchiveProviderCredentialUseCase,
    ArchiveProviderModelUseCase,
    ProviderCredentialUsageUseCase,
    ProviderModelUsageUseCase,
    RevokeProviderCredentialUseCase,
    RotateProviderCredentialUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
    SQLAlchemyAgentRepositoryWithProviderModels,
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.model_lifecycle_controller import ModelLifecycleController
from shared.infra.transactional_handler import TransactionalHandler


def provider_model_usage_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    provider_model_repo = SQLAlchemyProviderModelRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    use_case = ProviderModelUsageUseCase(
        provider_model_repo,
        agent_repo,
        release_repo,
        dependency_reader=build_provider_dependency_reader(uow),
    )
    controller = ModelLifecycleController(use_case, path_param="provider_model_id")
    return TransactionalHandler(uow, controller.handle)


def archive_provider_model_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    provider_model_repo = SQLAlchemyProviderModelRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    usage_use_case = ProviderModelUsageUseCase(
        provider_model_repo,
        agent_repo,
        release_repo,
        dependency_reader=build_provider_dependency_reader(uow),
    )
    use_case = ArchiveProviderModelUseCase(provider_model_repo, usage_use_case)
    controller = ModelLifecycleController(use_case, path_param="provider_model_id")
    return TransactionalHandler(uow, controller.handle)


def credential_usage_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    provider_model_repo = SQLAlchemyProviderModelRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    use_case = ProviderCredentialUsageUseCase(
        credential_repo,
        provider_model_repo,
        agent_repo,
        release_repo,
        dependency_reader=build_provider_dependency_reader(uow),
    )
    controller = ModelLifecycleController(use_case, path_param="credential_id")
    return TransactionalHandler(uow, controller.handle)


def rotate_credential_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    use_case = RotateProviderCredentialUseCase(
        credential_repo,
        SETTINGS.encryption_key,
    )
    controller = ModelLifecycleController(
        use_case,
        path_param="credential_id",
        body=True,
    )
    return TransactionalHandler(uow, controller.handle)


def revoke_credential_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    use_case = RevokeProviderCredentialUseCase(credential_repo)
    controller = ModelLifecycleController(
        use_case,
        path_param="credential_id",
        body=True,
    )
    return TransactionalHandler(uow, controller.handle)


def archive_credential_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    provider_model_repo = SQLAlchemyProviderModelRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    usage_use_case = ProviderCredentialUsageUseCase(
        credential_repo,
        provider_model_repo,
        agent_repo,
        release_repo,
        dependency_reader=build_provider_dependency_reader(uow),
    )
    use_case = ArchiveProviderCredentialUseCase(credential_repo, usage_use_case)
    controller = ModelLifecycleController(use_case, path_param="credential_id")
    return TransactionalHandler(uow, controller.handle)
