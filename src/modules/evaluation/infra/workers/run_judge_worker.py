from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.run_judge import (
    selected_judge_config,
    selected_judge_provider_model_id,
)
from modules.evaluation.infra.database.models import EvaluationRunModel
from modules.evaluation.infra.runtime_safe_judge import RuntimeSafeEvaluatorModelGateway
from modules.evaluation.infra.workers.integrity_worker import (
    IntegrityEvaluationRunProcessor,
    IntegrityEvaluationRunWorker,
)
from shared.infra.config import Settings


def effective_suite_for_run(run: Any, suite: Any) -> Any:
    """Project the immutable Suite rules with the Judge frozen on this Run."""

    return SimpleNamespace(
        judge_provider_model_id=selected_judge_provider_model_id(
            run,
            suite.judge_provider_model_id,
        ),
        judge_config=selected_judge_config(run, suite.judge_config),
        rubric=suite.rubric,
        deterministic_checks=suite.deterministic_checks,
    )


class RunJudgeEvaluationRunProcessor(IntegrityEvaluationRunProcessor):
    """Execute exactly the Judge protocol selected and frozen when the Run was created."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings | None = None,
    ) -> None:
        super().__init__(session_factory, settings=settings)
        self._judge = RuntimeSafeEvaluatorModelGateway(settings)

    async def _execute_trial(self, trial, target, case, suite) -> None:
        async with self._session_factory() as session:
            run = await session.get(EvaluationRunModel, trial.evaluation_run_id)
        effective_suite = effective_suite_for_run(run, suite) if run is not None else suite
        await super()._execute_trial(trial, target, case, effective_suite)


class RunJudgeEvaluationRunWorker(IntegrityEvaluationRunWorker):
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
        self._processor = RunJudgeEvaluationRunProcessor(
            session_factory,
            settings=settings,
        )


__all__ = [
    "RunJudgeEvaluationRunProcessor",
    "RunJudgeEvaluationRunWorker",
    "effective_suite_for_run",
]
