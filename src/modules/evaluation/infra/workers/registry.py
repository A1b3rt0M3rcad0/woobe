from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from modules.evaluation.infra.workers.slot_ready_authoring_worker import (
    SlotReadyEvaluationAuthoringWorker,
)
from modules.evaluation.infra.workers.variant_worker import (
    VariantAwareConcurrentEvaluationRunWorker,
)
from shared.infra.config import Settings
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol


class EvaluationWorkerRegistry:
    def __init__(self) -> None:
        self._workers: list[WorkerProtocol] = []

    def register(self, worker: WorkerProtocol) -> None:
        self._workers.append(worker)

    def iter_workers(self) -> list[WorkerProtocol]:
        return list(self._workers)


def register_evaluation_workers(
    registry: EvaluationWorkerRegistry,
    settings: Settings | None = None,
    engine: AsyncEngine | None = None,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    del rabbitmq_manager
    if engine is None:
        return
    resolved_settings = settings or Settings()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    registry.register(
        VariantAwareConcurrentEvaluationRunWorker(
            session_factory,
            settings=resolved_settings,
        )
    )
    registry.register(
        SlotReadyEvaluationAuthoringWorker(
            session_factory,
            settings=resolved_settings,
        )
    )


_check: WorkerRegistryProtocol = EvaluationWorkerRegistry()
del _check
