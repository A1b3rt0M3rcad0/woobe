from __future__ import annotations

from modules.evaluation.infra.adaptive_judge import AdaptiveEvaluatorModelGateway
from modules.evaluation.infra.budgeted_judge import BudgetedEvaluatorModelGateway
from modules.evaluation.infra.governed_budgeted_judge import (
    GovernedBudgetedEvaluatorModelGateway,
)
from modules.evaluation.infra.governed_judge import GovernedEvaluatorModelGateway


def test_context_budgeting_runs_before_governed_provider_execution() -> None:
    mro = GovernedBudgetedEvaluatorModelGateway.mro()

    assert mro.index(BudgetedEvaluatorModelGateway) < mro.index(
        GovernedEvaluatorModelGateway
    )
    assert mro.index(GovernedEvaluatorModelGateway) < mro.index(
        AdaptiveEvaluatorModelGateway
    )
