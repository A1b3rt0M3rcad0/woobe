from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.network.background_boundary import AgentInvoker
from modules.network.background_boundary import AgentInvocationArtifactMaterializer
from modules.network.background_boundary import NetworkRuntimeFinalizer
from modules.network.background_boundary import NetworkRuntimeLoader
from modules.network.background_boundary import RedisNetworkExecutionStore
from woobe_workers.consumers.network.execution_worker import (
    NetworkExecutionConsumer,
    NetworkExecutionProcessor,
    NetworkLeaseRecoveryWorker,
)
from woobe_workers.consumers.network.outbox_dispatcher import NetworkOutboxDispatcherWorker
from shared.composition_resources import EXECUTION_STATE_STORE, SESSION_FACTORY
from woobe_workers.settings import WorkerSettings
from shared.infra.rabbitmq import RabbitMQManager
from woobe_workers.contracts import WorkerProtocol, WorkerRegistryProtocol

AgentInvokerFactory = Callable[[WorkerSettings], AgentInvoker]
AgentArtifactMaterializerFactory = Callable[[], AgentInvocationArtifactMaterializer]
_AGENT_INVOKER_FACTORY: AgentInvokerFactory | None = None
_AGENT_ARTIFACT_MATERIALIZER_FACTORY: AgentArtifactMaterializerFactory | None = None


def configure_network_agent_invoker_factory(
    factory: AgentInvokerFactory | None,
) -> None:
    global _AGENT_INVOKER_FACTORY
    _AGENT_INVOKER_FACTORY = factory


def configure_network_agent_artifact_materializer_factory(
    factory: AgentArtifactMaterializerFactory | None,
) -> None:
    global _AGENT_ARTIFACT_MATERIALIZER_FACTORY
    _AGENT_ARTIFACT_MATERIALIZER_FACTORY = factory


class NetworkWorkerRegistry:
    def __init__(self) -> None:
        self._workers: list[WorkerProtocol] = []

    def register(self, worker: WorkerProtocol) -> None:
        self._workers.append(worker)

    def iter_workers(self) -> list[WorkerProtocol]:
        return list(self._workers)


def register_network_workers(
    registry: NetworkWorkerRegistry,
    settings: WorkerSettings,
    engine: AsyncEngine,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    if rabbitmq_manager is None or not settings.network_runtime_enabled:
        return
    if _AGENT_INVOKER_FACTORY is None:
        raise RuntimeError(
            "Network Agent runtime adapter is not configured by the worker composition root"
        )
    if _AGENT_ARTIFACT_MATERIALIZER_FACTORY is None:
        raise RuntimeError(
            "Network Agent artifact materializer is not configured by the worker composition root"
        )

    loader = NetworkRuntimeLoader(SESSION_FACTORY)
    finalizer = NetworkRuntimeFinalizer(
        SESSION_FACTORY,
        agent_artifact_materializer=_AGENT_ARTIFACT_MATERIALIZER_FACTORY(),
    )
    state_store = RedisNetworkExecutionStore(EXECUTION_STATE_STORE)
    processor = NetworkExecutionProcessor(
        loader=loader,
        store=state_store,
        finalizer=finalizer,
        agent_invoker=_AGENT_INVOKER_FACTORY(settings),
        lease_ttl_seconds=settings.network_execution_lease_ttl_seconds,
        heartbeat_seconds=settings.network_execution_lease_heartbeat_seconds,
    )
    registry.register(
        NetworkOutboxDispatcherWorker(
            engine,
            rabbitmq_manager,
            batch_size=settings.outbox_batch_size,
        )
    )
    registry.register(
        NetworkExecutionConsumer(
            rabbitmq_manager,
            processor,
            prefetch_count=settings.network_worker_prefetch,
            worker_slots=settings.network_worker_slots,
        )
    )
    registry.register(
        NetworkLeaseRecoveryWorker(
            loader=loader,
            store=state_store,
            finalizer=finalizer,
            lease_ttl_seconds=settings.network_execution_lease_ttl_seconds,
        )
    )


_check: WorkerRegistryProtocol = NetworkWorkerRegistry()
del _check
