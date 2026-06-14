"""Deprecated - domain worker orchestration removed (spec 061).

The generic WorkerRunner lives in src/shared/workers/runner.py.
Module-specific workers are exposed via module registries (specs 062-063).
This file is kept as a compatibility shim during the migration.
"""
import asyncio
import logging
import sys
import warnings

from shared.workers.runner import WorkerRunner
from workers import (
    InboxConsumerWorker,
    OutboxPublisherWorker,
)

warnings.warn(
    "workers.runner is deprecated. Use shared.workers.runner.WorkerRunner with module registries.",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)


async def run_all_workers_deprecated(settings=None) -> None:
    from shared.infra.config import Settings
    from shared.infra.database.session import create_engine
    from shared.infra.rabbitmq import RabbitMQManager

    s = settings or Settings()
    engine = create_engine(s)

    async with RabbitMQManager(s.rabbitmq_url, s.rabbitmq_exchange) as rmq:
        publisher = OutboxPublisherWorker(engine, rmq)
        consumer = InboxConsumerWorker(engine, rmq)
        runner = WorkerRunner(workers=[publisher, consumer])
        try:
            await runner.run_once()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.warning(
        "workers.runner is deprecated. Use shared.workers.runner.WorkerRunner."
    )

    match sys.argv[1] if len(sys.argv) > 1 else "all":
        case "all":
            asyncio.run(run_all_workers_deprecated())
        case _:
            print(
                "Deprecated runner. Only 'all' is supported as compatibility shim.\n"
                "Use module-specific worker registries (specs 062-063)."
            )
            sys.exit(1)
