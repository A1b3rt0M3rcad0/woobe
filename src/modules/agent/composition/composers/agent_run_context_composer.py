from __future__ import annotations

from collections.abc import Callable

from modules.agent.composition.factories.agent_uow_factory import (
    build_agent_read_uow,
    build_agent_uow,
)
from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner
from modules.agent.infra.execution.agent_run_context_service import AgentRunContextReadService
from modules.agent.presentation.http.controllers.agent_run_context_controller import (
    AgentRunContextController,
)


def agent_run_context_composer() -> Callable:
    transactions = AgentRuntimeTransactionRunner(
        build_agent_uow,
        build_agent_read_uow,
    )
    return AgentRunContextController(
        AgentRunContextReadService(transactions)
    ).list_model_invocations
