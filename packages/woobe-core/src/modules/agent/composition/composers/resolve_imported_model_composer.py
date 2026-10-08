from modules.agent.application.use_cases.resolve_imported_model import (
    ResolveImportedModelUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.resolve_imported_model_controller import (
    ResolveImportedModelController,
)
from shared.infra.transactional_handler import TransactionalHandler


def resolve_imported_model_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    use_case = ResolveImportedModelUseCase(
        SQLAlchemyProviderModelRepository(uow),
        SQLAlchemyProviderCredentialRepository(uow),
    )
    return TransactionalHandler(uow, ResolveImportedModelController(use_case).handle)
