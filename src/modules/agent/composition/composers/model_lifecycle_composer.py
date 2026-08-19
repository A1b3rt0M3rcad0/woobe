from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.provider_management_cases import (
    ArchiveProviderCredentialUseCase,
    ArchiveProviderModelUseCase,
    ProviderCredentialUsageUseCase,
    ProviderModelUsageUseCase,
    RevokeProviderCredentialUseCase,
    RotateProviderCredentialUseCase,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.model_lifecycle_controller import ModelLifecycleController
from shared.infra.transactional_handler import TransactionalHandler


def _model_usage(uow: AgentUnitOfWork) -> ProviderModelUsageUseCase:
    return ProviderModelUsageUseCase(uow.provider_models, uow.agents, uow.releases)


def _credential_usage(uow: AgentUnitOfWork) -> ProviderCredentialUsageUseCase:
    return ProviderCredentialUsageUseCase(
        uow.provider_credentials,
        uow.provider_models,
        uow.agents,
        uow.releases,
    )


def provider_model_usage_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    controller = ModelLifecycleController(_model_usage(uow), path_param="provider_model_id")
    return TransactionalHandler(uow, controller.handle)


def archive_provider_model_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ArchiveProviderModelUseCase(uow.provider_models, _model_usage(uow))
    controller = ModelLifecycleController(use_case, path_param="provider_model_id")
    return TransactionalHandler(uow, controller.handle)


def credential_usage_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    controller = ModelLifecycleController(_credential_usage(uow), path_param="credential_id")
    return TransactionalHandler(uow, controller.handle)


def rotate_credential_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = RotateProviderCredentialUseCase(uow.provider_credentials)
    controller = ModelLifecycleController(use_case, path_param="credential_id", body=True)
    return TransactionalHandler(uow, controller.handle)


def revoke_credential_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = RevokeProviderCredentialUseCase(uow.provider_credentials)
    controller = ModelLifecycleController(use_case, path_param="credential_id", body=True)
    return TransactionalHandler(uow, controller.handle)


def archive_credential_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ArchiveProviderCredentialUseCase(uow.provider_credentials, _credential_usage(uow))
    controller = ModelLifecycleController(use_case, path_param="credential_id")
    return TransactionalHandler(uow, controller.handle)
