from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Sequence

from modules.agent.background_boundary import (
    AgentRunEventProjector,
    AgentRuntimeTransactionRunner,
    AgentUnitOfWork,
    HttpToolExecutor,
    close_http_tool_executor,
    configure_http_tool_executor,
)
from modules.network.background_boundary import (
    NetworkRunEventProjector,
    NetworkRuntimeFinalizer,
)
from shared.composition_resources import (
    RUN_EVENT_BUFFER,
    RUN_EVENT_JOURNAL,
    SESSION_FACTORY,
)
from shared.infra.database.session import create_engine
from shared.infra.rabbitmq import RabbitMQManager
from shared.observability.logging_config import configure_logging
from woobe_workers.composition.network_agent_persistence import (
    ProjectRAIAgentInvocationArtifactMaterializer,
)
from woobe_workers.composition.network_agent_runtime import ProjectRAIAgentInvoker
from woobe_workers.composition.registries import (
    build_registries,
    discover_module_entries,
)
from woobe_workers.consumers.network.registry import (
    configure_network_agent_artifact_materializer_factory,
    configure_network_agent_invoker_factory,
)
from woobe_workers.contracts import ModuleWorkerEntry, WorkerProtocol
from woobe_workers.runtime.run_event_persistence_worker import RunEventPersistenceWorker
from woobe_workers.runtime.runner import WorkerRunner
from woobe_workers.settings import WorkerSettings

logger = logging.getLogger(__name__)


class _CompositeRunEventProjector:
    def __init__(self, *projectors) -> None:
        self._projectors = projectors

    async def project(self, events) -> None:
        for projector in self._projectors:
            await projector.project(events)


def _configure_logging(settings: WorkerSettings) -> None:
    configure_logging(level=settings.log_level, json_logs=settings.json_logs)


def _configure_http_tool_runtime(settings: WorkerSettings) -> HttpToolExecutor:
    executor = HttpToolExecutor(
        default_timeout_ms=settings.http_tool_timeout_max_ms,
        max_timeout_ms=settings.http_tool_timeout_max_ms,
        max_response_bytes=settings.http_tool_response_max_bytes,
        allow_local_networks=settings.http_tool_allow_local_networks,
    )
    configure_http_tool_executor(executor)
    return executor


def _build_runtime_workers(settings: WorkerSettings, engine) -> list[WorkerProtocol]:
    if settings.run_persistence_mode != "event_journal":
        return []
    if RUN_EVENT_BUFFER is None or RUN_EVENT_JOURNAL is None:
        raise RuntimeError(
            "event_journal worker runtime requires WOOBE_REDIS_URL and WOOBE_MONGODB_URL"
        )
    transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))
    network_finalizer = NetworkRuntimeFinalizer(
        SESSION_FACTORY,
        agent_artifact_materializer=ProjectRAIAgentInvocationArtifactMaterializer(),
    )
    projector = _CompositeRunEventProjector(
        AgentRunEventProjector(transactions),
        NetworkRunEventProjector(
            SESSION_FACTORY,
            journal=RUN_EVENT_JOURNAL,
            finalizer=network_finalizer,
        ),
    )
    return [
        RunEventPersistenceWorker(
            buffer=RUN_EVENT_BUFFER,
            journal=RUN_EVENT_JOURNAL,
            projector=projector,
            consumer_group=settings.run_event_redis_consumer_group,
            batch_size=settings.run_event_batch_size,
            flush_interval_ms=settings.run_event_flush_interval_ms,
            claim_idle_seconds=settings.run_event_claim_idle_seconds,
        )
    ]


def _install_shutdown_handlers(
    stop_event: asyncio.Event,
) -> tuple[asyncio.AbstractEventLoop, list[signal.Signals]]:
    loop = asyncio.get_running_loop()
    installed: list[signal.Signals] = []

    def request_shutdown(received_signal: signal.Signals) -> None:
        logger.info("Worker runtime received %s", received_signal.name)
        stop_event.set()

    for received_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                received_signal,
                request_shutdown,
                received_signal,
            )
            installed.append(received_signal)
        except NotImplementedError:
            logger.warning(
                "Signal handlers are not supported by this event loop: %s",
                received_signal.name,
            )

    return loop, installed


async def run_workers(
    settings: WorkerSettings | None = None,
    *,
    extra_entries: Sequence[ModuleWorkerEntry] = (),
) -> None:
    runtime_settings = settings or WorkerSettings()
    _configure_logging(runtime_settings)

    engine = create_engine(runtime_settings)
    rabbitmq_manager = RabbitMQManager(
        url=runtime_settings.rabbitmq_url,
        exchange_name=runtime_settings.rabbitmq_exchange,
    )
    runner: WorkerRunner | None = None
    stop_event = asyncio.Event()
    loop, installed_signals = _install_shutdown_handlers(stop_event)

    try:
        http_executor = _configure_http_tool_runtime(runtime_settings)
        configure_network_agent_invoker_factory(
            lambda worker_settings: ProjectRAIAgentInvoker(
                worker_settings,
                http_executor,
            )
        )
        configure_network_agent_artifact_materializer_factory(
            ProjectRAIAgentInvocationArtifactMaterializer
        )
        async with engine.begin() as conn:
            await conn.run_sync(lambda _: None)

        await rabbitmq_manager.connect()

        entries = discover_module_entries()
        entries.extend(extra_entries)
        registries = build_registries(
            entries,
            engine=engine,
            settings=runtime_settings,
            rabbitmq_manager=rabbitmq_manager,
        )
        runtime_workers = _build_runtime_workers(runtime_settings, engine)
        worker_count = (
            sum(len(registry.iter_workers()) for registry in registries)
            + len(runtime_workers)
        )
        runner = WorkerRunner.from_registries(
            registries,
            extra_workers=runtime_workers,
        )
        await runner.start()

        logger.info(
            "Worker runtime started with %d registries and %d workers",
            len(registries),
            worker_count,
        )
        await stop_event.wait()
    finally:
        configure_network_agent_artifact_materializer_factory(None)
        configure_network_agent_invoker_factory(None)
        if runner is not None:
            await runner.stop()
        await rabbitmq_manager.close()
        await close_http_tool_executor()
        await engine.dispose()
        for installed_signal in installed_signals:
            loop.remove_signal_handler(installed_signal)
        logger.info("Worker runtime stopped")


def main() -> None:
    try:
        asyncio.run(run_workers())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
