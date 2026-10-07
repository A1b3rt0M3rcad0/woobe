from modules.agent.application.development_tool_projection import (
    development_tool_projection,
)
from modules.agent.application.use_cases.ai_prompt_cases import CreatePromptUseCase
from modules.agent.application.use_cases.ai_contract_cases import CreateContractUseCase
from modules.agent.application.use_cases.materialize_development_artifact import (
    MaterializeDevelopmentArtifact,
)
from modules.agent.application.dtos.ai_dtos import (
    CreatePromptOutput,
    CreateContractOutput,
)
from modules.agent.infra.database.development_resource_reader import (
    DevelopmentResourceReader,
)
from modules.agent.infra.database.development_resources import SQLDevelopmentResources
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentPromptRepository,
    SQLAlchemyAgentContractRepository,
    SQLAlchemyDocumentCollectionRepository,
    SQLAlchemyAgentOutboxEventWriter,
)
from modules.agent.infra.database.document_repositories import (
    SQLAlchemyGuardedDocumentRepository,
)
from modules.agent.application.use_cases import (
    CreateCollectionUseCase,
    UploadDocumentUseCase,
)
from modules.agent.presentation.controllers.create_collection_controller import (
    CreateCollectionController,
)
from modules.agent.presentation.controllers.upload_document_controller import (
    UploadDocumentController,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.presentation.controllers.development_resource_controller import (
    DevelopmentResourceController,
)
from modules.agent.presentation.controllers.create_prompt_version_controller import (
    CreatePromptVersionController,
)
from modules.agent.presentation.controllers.create_contract_version_controller import (
    CreateContractVersionController,
)
from shared.infra.transactional_handler import TransactionalHandler


def build_development_resource_reader():
    return DevelopmentResourceReader(development_tool_projection)


def _build_development_controller(uow, action, artifact=False):
    resources = SQLDevelopmentResources(uow, build_development_resource_reader())
    fallback = None
    if artifact:
        repository = (
            SQLAlchemyAgentPromptRepository(uow)
            if action == "Prompt"
            else SQLAlchemyAgentContractRepository(uow)
        )
        materialize = MaterializeDevelopmentArtifact(
            repository,
            CreatePromptUseCase(repository)
            if action == "Prompt"
            else CreateContractUseCase(repository),
            CreatePromptOutput if action == "Prompt" else CreateContractOutput,
            ("name", "content", "content_hash")
            if action == "Prompt"
            else (
                "name",
                "input_schema",
                "output_schema",
                "validation_mode",
                "repair_attempts",
                "additional_instructions",
                "schema_hash",
            ),
        )
        fallback = (
            CreatePromptVersionController(materialize)
            if action == "Prompt"
            else CreateContractVersionController(materialize)
        )
    controller = DevelopmentResourceController(resources, action, fallback)
    return controller


def prepare_existing_agent_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    controller = _build_development_controller(uow, "prepare_existing")
    return TransactionalHandler(uow, controller.handle)


def reuse_development_resource_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    controller = _build_development_controller(uow, "reuse")
    return TransactionalHandler(uow, controller.handle)


def reuse_frozen_agent_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    controller = _build_development_controller(uow, "reuse_frozen")
    return TransactionalHandler(uow, controller.handle)


def materialize_development_prompt_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    controller = _build_development_controller(uow, "Prompt", artifact=True)
    return TransactionalHandler(uow, controller.handle)


def materialize_development_contract_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    controller = _build_development_controller(uow, "Contract", artifact=True)
    return TransactionalHandler(uow, controller.handle)


def materialize_development_collection_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    resources = SQLDevelopmentResources(uow, build_development_resource_reader())
    fallback = CreateCollectionController(
        CreateCollectionUseCase(
            SQLAlchemyDocumentCollectionRepository(uow),
            SQLAlchemyAgentOutboxEventWriter(uow),
        )
    )
    controller = DevelopmentResourceController(resources, "Collection", fallback)
    return TransactionalHandler(uow, controller.handle)


def materialize_development_document_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    resources = SQLDevelopmentResources(uow, build_development_resource_reader())
    fallback = UploadDocumentController(
        UploadDocumentUseCase(
            SQLAlchemyGuardedDocumentRepository(uow),
            SQLAlchemyDocumentCollectionRepository(uow),
            SQLAlchemyAgentOutboxEventWriter(uow),
        )
    )
    controller = DevelopmentResourceController(resources, "Document", fallback)
    return TransactionalHandler(uow, controller.handle)


def find_development_document_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    resources = SQLDevelopmentResources(uow, build_development_resource_reader())
    controller = DevelopmentResourceController(resources, "DocumentLookup")
    return TransactionalHandler(uow, controller.handle)
