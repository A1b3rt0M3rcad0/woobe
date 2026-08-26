from __future__ import annotations

from collections.abc import Callable

from modules.agent.composition.factories.agent_uow_factory import (
    build_agent_read_uow,
    build_agent_uow,
)
from modules.agent.composition.resources import EXECUTION_STATE_STORE
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.infra.execution.agent_run_reattach_service import (
    AgentRunReattachService,
)
from modules.agent.presentation.http.controllers.agent_run_reattach_controller import (
    AgentRunReattachController,
)


def _build_controller() -> AgentRunReattachController:
    transactions = AgentRuntimeTransactionRunner(
        build_agent_uow,
        build_agent_read_uow,
    )
    service = AgentRunReattachService(
        transactions=transactions,
        state_store=EXECUTION_STATE_STORE,
    )
    return AgentRunReattachController(service)


def active_agent_run_composer() -> Callable:
    return _build_controller().active


def attach_agent_run_composer() -> Callable:
    return _build_controller().attach


def cancel_agent_run_composer() -> Callable:
    return _build_controller().cancel
