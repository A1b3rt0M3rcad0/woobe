"""Public host boundary for network background execution.

This module is the only supported surface through which external process hosts
may consume network background capabilities. It contains no worker
lifecycle, registry, polling, slot or process-bootstrap behavior.
"""

from modules.network.application.runtime import (
    AgentInvocationResult,
    AgentInvoker,
    InternalDelegationTool,
    NetworkBudgetExceeded,
    NetworkExecutionCancelled,
    NetworkExecutor,
)
from modules.network.application.structured_output_persistence import (
    install_structured_output_persistence,
)
from modules.network.application.runtime_failures import (
    NetworkRuntimeFailure,
    classify_runtime_exception,
)
from modules.network.infra.database.models import (
    NetworkOutboxEventModel,
)
from modules.network.infra.runtime.agent_artifacts import (
    AgentInvocationArtifact,
    AgentInvocationArtifactMaterializer,
)
from modules.network.infra.runtime.finalizer import (
    NetworkRuntimeFinalizer,
)
from modules.network.infra.runtime.journal_store import (
    JournaledRedisNetworkExecutionStore,
)
from modules.network.infra.runtime.loader import (
    NetworkRuntimeLoader,
)
from modules.network.infra.runtime.redis_store import (
    RedisNetworkExecutionStore,
)
from modules.network.infra.runtime.run_event_projector import (
    NetworkRunEventProjector,
)
from modules.network.infra.runtime.run_persistence import (
    NetworkJournalTerminalFinalizer,
    NetworkRunPersistenceFinalizer,
)

install_structured_output_persistence()

__all__ = [
    "AgentInvocationArtifact",
    "AgentInvocationArtifactMaterializer",
    "AgentInvocationResult",
    "AgentInvoker",
    "InternalDelegationTool",
    "JournaledRedisNetworkExecutionStore",
    "NetworkBudgetExceeded",
    "NetworkExecutionCancelled",
    "NetworkExecutor",
    "NetworkJournalTerminalFinalizer",
    "NetworkOutboxEventModel",
    "NetworkRunEventProjector",
    "NetworkRunPersistenceFinalizer",
    "NetworkRuntimeFailure",
    "NetworkRuntimeFinalizer",
    "NetworkRuntimeLoader",
    "RedisNetworkExecutionStore",
    "classify_runtime_exception",
]
