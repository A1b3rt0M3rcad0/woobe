from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.infra.database.models import (
    EvaluationTargetModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
)
from modules.evaluation.infra.workers.concurrent_worker import (
    ConcurrentOutcomeAwareEvaluationRunProcessor,
    ConcurrentOutcomeAwareEvaluationRunWorker,
)
from shared.infra.config import Settings


class VariantAwareConcurrentEvaluationRunProcessor(
    ConcurrentOutcomeAwareEvaluationRunProcessor
):
    """Execute model comparison variants from the immutable derived snapshot."""

    async def _execute_agent(
        self,
        trial: EvaluationTrialModel,
        target: EvaluationTargetModel,
        case: EvaluationTestCaseModel,
    ) -> tuple[dict[str, Any], dict[str, Any], None, UUID | None]:
        snapshot = target.snapshot or {}
        if not isinstance(snapshot.get("evaluation_variant"), dict):
            return await super()._execute_agent(trial, target, case)

        # The canonical Agent runtime applies snapshot_override for draft-style
        # invocations. A lightweight proxy keeps the persisted target provenance
        # unchanged while executing the frozen derived configuration.
        runtime_target = SimpleNamespace(
            entity_id=target.entity_id,
            agent_release_id=None,
            snapshot=snapshot,
            source_type="draft",
            side=target.side,
        )
        return await super()._execute_agent(trial, runtime_target, case)


class VariantAwareConcurrentEvaluationRunWorker(
    ConcurrentOutcomeAwareEvaluationRunWorker
):
    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings | None = None,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(
            session_factory,
            settings=settings,
            worker_id=worker_id,
        )
        self._processor = VariantAwareConcurrentEvaluationRunProcessor(
            session_factory,
            settings=settings,
        )


__all__ = [
    "VariantAwareConcurrentEvaluationRunProcessor",
    "VariantAwareConcurrentEvaluationRunWorker",
]
