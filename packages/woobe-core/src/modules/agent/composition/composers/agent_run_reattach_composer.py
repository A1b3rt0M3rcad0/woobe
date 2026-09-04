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


def _build_operations() -> AgentRunReattachService:
    transactions = AgentRuntimeTransactionRunner(
        build_agent_uow,
        build_agent_read_uow,
    )
    return AgentRunReattachService(
        transactions=transactions,
        state_store=EXECUTION_STATE_STORE,
    )


def active_agent_run_composer() -> Callable:
    return _build_operations().active


def attach_agent_run_composer() -> Callable:
    return _build_operations().stream_sse


def cancel_agent_run_composer() -> Callable:
    return _build_operations().cancel
