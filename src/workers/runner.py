import asyncio
import logging
import signal
import sys
from typing import Never

from sqlalchemy.ext.asyncio import AsyncEngine

from shared.infra.config import Settings
from shared.infra.database.session import create_engine
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.base_worker import BaseWorker
from workers import (
    InboxConsumerWorker,
    InboxDispatcherWorker,
    OutboxPublisherWorker,
)
from workers.dispatcher import build_dispatcher

logger = logging.getLogger(__name__)


def _build_engine(settings: Settings | None = None) -> tuple[AsyncEngine, Settings]:
    s = settings or Settings()
    return create_engine(s), s


async def run_once(
    worker_class: type[BaseWorker] | None = None,
    worker: BaseWorker | None = None,
    settings: Settings | None = None,
) -> None:
    engine, _ = _build_engine(settings)
    instance = worker or (worker_class(engine) if worker_class else None)
    if instance is None:
        raise ValueError("provide worker_class or worker instance")
    try:
        await instance.run()
    finally:
        await engine.dispose()


async def run_loop(
    worker_class: type[BaseWorker] | None = None,
    worker: BaseWorker | None = None,
    interval: float | None = None,
    settings: Settings | None = None,
) -> Never:
    engine, s = _build_engine(settings)
    if interval is None:
        interval = s.worker_interval
    instance = worker or (worker_class(engine) if worker_class else None)
    if instance is None:
        raise ValueError("provide worker_class or worker instance")

    stop = asyncio.Event()

    def _signal_handler() -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    try:
        while not stop.is_set():
            await instance.run()
            await asyncio.sleep(interval)
    finally:
        await engine.dispose()
        sys.exit(0)


async def run_all_workers(settings: Settings | None = None) -> None:
    engine, s = _build_engine(settings)

    async with RabbitMQManager(s.rabbitmq_url, s.rabbitmq_exchange) as rmq:
        publisher = OutboxPublisherWorker(engine, rmq)
        consumer = InboxConsumerWorker(engine, rmq)
        dispatcher = build_dispatcher(engine)

        try:
            await publisher.run()
            await consumer.run()
            await dispatcher.run()
        finally:
            await engine.dispose()


async def run_publisher(settings: Settings | None = None) -> None:
    engine, s = _build_engine(settings)
    async with RabbitMQManager(s.rabbitmq_url, s.rabbitmq_exchange) as rmq:
        worker = OutboxPublisherWorker(engine, rmq)
        try:
            await worker.run()
        finally:
            await engine.dispose()


async def run_consumer(settings: Settings | None = None) -> None:
    engine, s = _build_engine(settings)
    async with RabbitMQManager(s.rabbitmq_url, s.rabbitmq_exchange) as rmq:
        worker = InboxConsumerWorker(engine, rmq)
        try:
            await worker.run()
        finally:
            await engine.dispose()


async def run_dispatcher(settings: Settings | None = None) -> None:
    engine, s = _build_engine(settings)
    worker = build_dispatcher(engine)
    try:
        await worker.run()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    match sys.argv[1] if len(sys.argv) > 1 else "all":
        case "publisher":
            asyncio.run(run_publisher())
        case "consumer":
            asyncio.run(run_consumer())
        case "dispatcher":
            asyncio.run(run_dispatcher())
        case "all":
            asyncio.run(run_all_workers())
        case _:
            print("Usage: python -m workers.runner [publisher|consumer|dispatcher|all]")
            sys.exit(1)
