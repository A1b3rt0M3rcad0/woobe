from modules.agent.infra.execution.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)
from modules.agent.infra.execution.transaction_bounded_rag import (
    TransactionBoundedVectorSnapshotRAGMixin,
)


class TransactionBoundedStructuredOutputAskAgentUseCase(
    TransactionBoundedVectorSnapshotRAGMixin,
    StructuredOutputAskAgentUseCase,
):
    """Structured Agent runtime with external I/O outside DB transactions."""

    pass
