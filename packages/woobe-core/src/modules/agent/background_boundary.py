"""Public host boundary for agent background execution.

This module is the only supported surface through which external process hosts
may consume agent background capabilities. It contains no worker
lifecycle, worker registry, polling, slot or process-bootstrap behavior.
"""

from modules.agent.application.context_assembler_registry import (
    build_runtime_context_assembler,
)
from modules.agent.application.dtos.runtime_dtos import (
    AskInput,
)
from modules.agent.application.interfaces.embedding_errors import (
    EmbeddingProviderError,
)
from modules.agent.application.use_cases.vector_snapshot_use_cases import (
    BuildVectorSnapshotUseCase,
)
from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_agent_run_recovery_executor,
)
from modules.agent.domain.entities import (
    AskJob,
)
from modules.agent.domain.events import (
    AgentExecutionFailedV1,
)
from modules.agent.domain.vector_snapshot_entities import (
    VECTOR_SNAPSHOT_BUILDING,
    VECTOR_SNAPSHOT_STAGE_QUEUED,
)
from modules.agent.infra.adapters.http_tool_runtime import (
    close_http_tool_executor,
    configure_http_tool_executor,
)
from modules.agent.infra.adapters.langchain_embedding_factory import (
    LangchainEmbeddingFactory,
)
from modules.agent.infra.adapters.langchain_llm_factory import (
    LangchainLLMFactory,
)
from modules.agent.infra.adapters.tool_executor import (
    HttpToolExecutor,
)
from modules.agent.infra.database.context_evidence_store import (
    ContextEvidenceStore,
)
from modules.agent.infra.database.models import (
    AgentInboxEventModel,
    AgentOutboxEventModel,
    MessageModel,
    SessionModel,
)
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.repositories import (
    AGENT_DEFAULT_BATCH_SIZE,
    AGENT_OUTBOX_LOCK_TIMEOUT_SECONDS,
    SQLAlchemyAgentInboxRepository,
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyAgentOutboxRepository,
    SQLAlchemyAskJobRepository,
    SQLAlchemyDocumentRepository,
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.run_models import (
    AgentRunModel,
)
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.infra.database.unit_of_work import (
    AgentUnitOfWork,
)
from modules.agent.infra.database.vector_snapshot_models import (
    VectorSnapshotModel,
)
from modules.agent.infra.database.vector_snapshot_repositories import (
    SQLAlchemyVectorSnapshotRepository,
)
from modules.agent.infra.execution.agent_run_recovery_runtime import (
    AgentRunRecoveryExecutor,
    AgentRunRecoveryRequest,
)
from modules.agent.infra.execution.agent_tool_runtime_gateway import (
    AgentToolRuntimeGateway,
)
from modules.agent.infra.execution.run_event_projector import (
    AgentRunEventProjector,
)
from modules.agent.infra.execution.transaction_bounded_structured_output import (
    TransactionBoundedStructuredOutputRuntime,
)
from modules.agent.infra.messaging.event_mappers import (
    RabbitMQMessageEnvelope,
    outbox_to_rabbit_message,
    rabbit_message_to_inbox,
)
from modules.agent.infra.messaging.publishers import (
    AgentRabbitMQPublisher,
)
from modules.agent.infra.storage.factory import (
    create_file_storage,
)