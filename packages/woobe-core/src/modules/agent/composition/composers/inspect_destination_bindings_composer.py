from modules.agent.application.use_cases.inspect_destination_bindings import (
    InspectDestinationBindingsUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.project_environment_reader import (
    SQLAlchemyProjectEnvironmentReader,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyProviderCredentialRepository,
    SQLAlchemyAgentToolSecretRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.vector_snapshot_repositories import (
    SQLAlchemyVectorSnapshotRepository,
)
from modules.agent.presentation.controllers.inspect_destination_bindings_controller import (
    InspectDestinationBindingsController,
)
from shared.infra.transactional_handler import TransactionalHandler


def inspect_destination_bindings_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    credentials = SQLAlchemyProviderCredentialRepository(uow)
    secrets = SQLAlchemyAgentToolSecretRepository(uow)
    vectors = SQLAlchemyVectorSnapshotRepository(uow)
    environment = SQLAlchemyProjectEnvironmentReader(uow)
    use_case = InspectDestinationBindingsUseCase(
        credentials, secrets, vectors, environment
    )
    controller = InspectDestinationBindingsController(use_case)
    return TransactionalHandler(uow, controller.handle)
