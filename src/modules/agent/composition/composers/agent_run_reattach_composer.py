from __future__ import annotations

from collections.abc import Callable

from modules.agent.composition.resources import EXECUTION_STATE_STORE, SESSION_FACTORY
from modules.agent.infra.execution.agent_run_reattach_service import (
    AgentRunReattachService,
)
from modules.agent.presentation.http.controllers.agent_run_reattach_controller import (
    AgentRunReattachController,
)


def active_agent_run_composer() -> Callable:
    service = AgentRunReattachService(
        session_factory=SESSION_FACTORY,
        state_store=EXECUTION_STATE_STORE,
    )
    controller = AgentRunReattachController(service)
    return controller.active


def attach_agent_run_composer() -> Callable:
    service = AgentRunReattachService(
        session_factory=SESSION_FACTORY,
        state_store=EXECUTION_STATE_STORE,
    )
    controller = AgentRunReattachController(service)
    return controller.attach


def cancel_agent_run_composer() -> Callable:
    service = AgentRunReattachService(
        session_factory=SESSION_FACTORY,
        state_store=EXECUTION_STATE_STORE,
    )
    controller = AgentRunReattachController(service)
    return controller.cancel
