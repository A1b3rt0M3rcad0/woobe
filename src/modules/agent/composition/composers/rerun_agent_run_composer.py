from __future__ import annotations

from collections.abc import Callable

from modules.agent.application.use_cases.rerun_agent_run import RerunAgentRunUseCase
from modules.agent.composition.factories.agent_uow_factory import build_agent_read_uow
from modules.agent.composition.factories.ask_agent_runtime_factory import build_ask_agent_use_case
from modules.agent.composition.resources import SETTINGS
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.database.agent_run_rerun_reader import SQLAlchemyAgentRunRerunReader
from modules.agent.presentation.controllers.rerun_agent_run_controller import RerunAgentRunController


def rerun_agent_run_composer() -> Callable:
    runtime, _transactions = build_ask_agent_use_case(
        SETTINGS,
        get_http_tool_executor(),
    )
    reader = SQLAlchemyAgentRunRerunReader(build_agent_read_uow)
    use_case = RerunAgentRunUseCase(reader, runtime)
    return RerunAgentRunController(use_case).handle
