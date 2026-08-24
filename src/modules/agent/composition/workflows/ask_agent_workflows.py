from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_ask_agent_handler,
    build_ask_agent_use_case,
)
from modules.agent.composition.resources import SETTINGS
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.runtime_environment_guard import (
    build_agent_runtime_environment_guard,
)
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.presentation.http.controllers.ask_agent_stream_controller import (
    AskAgentStreamController,
)
from shared.infra.workflow_handler import WorkflowHandler


def ask_agent_composer() -> WorkflowHandler:
    handler = build_ask_agent_handler(SETTINGS)
    return WorkflowHandler(handler)


def ask_agent_stream_composer() -> WorkflowHandler:
    use_case, transactions = build_ask_agent_use_case(
        SETTINGS,
        get_http_tool_executor(),
    )
    service = AskAgentStreamService(use_case, transactions)
    environment_guard = build_agent_runtime_environment_guard(transactions)
    controller = AskAgentStreamController(service, environment_guard)
    return WorkflowHandler(controller.handle)
