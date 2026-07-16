from __future__ import annotations

import asyncio
import logging
import signal

from shared.infra.config import Settings
from shared.infra.database.session import create_engine
from shared.infra.rabbitmq import RabbitMQManager
from shared.observability.logging_config import configure_logging
from shared.workers.discovery import build_registries, discover_module_entries
from shared.workers.runner import WorkerRunner

logger = logging.getLogger(__name__)


def _configure_logging(settings: Settings) -> None:
    configure_logging(level=settings.log_level, json_logs=settings.json_logs)


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


async def run_workers(settings: Settings | None = None) -> None:
    runtime_settings = settings or Settings()
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
        async with engine.begin() as conn:
            await conn.run_sync(lambda _: None)

        await rabbitmq_manager.connect()

        entries = discover_module_entries()
        registries = build_registries(
            entries,
            engine=engine,
            settings=runtime_settings,
            rabbitmq_manager=rabbitmq_manager,
        )
        worker_count = sum(len(registry.iter_workers()) for registry in registries)
        runner = WorkerRunner.from_registries(registries)
        await runner.start()

        logger.info(
            "Worker runtime started with %d registries and %d workers",
            len(registries),
            worker_count,
        )
        await stop_event.wait()
    finally:
        if runner is not None:
            await runner.stop()
        await rabbitmq_manager.close()
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
