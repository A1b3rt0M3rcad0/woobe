from __future__ import annotations

from modules.evaluation.infra.budgeted_judge import BudgetedEvaluatorModelGateway
from modules.evaluation.infra.governed_judge import GovernedEvaluatorModelGateway


class GovernedBudgetedEvaluatorModelGateway(
    BudgetedEvaluatorModelGateway,
    GovernedEvaluatorModelGateway,
):
    """Apply context compaction before governed provider execution and repair."""


__all__ = ["GovernedBudgetedEvaluatorModelGateway"]
