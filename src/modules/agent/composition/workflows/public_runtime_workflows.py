from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_agent_runtime_transactions,
    build_ask_agent_handler,
    build_ask_agent_use_case,
)
from modules.agent.composition.resources import SETTINGS
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.runtime_environment_guard import (
    build_agent_runtime_environment_guard,
)
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.public_runtime_request_gateway import (
    PublicRuntimeRequestGateway,
)
from modules.agent.presentation.controllers.public_runtime_controllers import (
    PublicRunController,
)
from modules.agent.presentation.http.controllers.public_runtime_stream_controller import (
    PublicRuntimeStreamController,
)
from shared.infra.workflow_handler import WorkflowHandler


def public_run_composer() -> WorkflowHandler:
    transactions = build_agent_runtime_transactions()
    preparer = PublicRuntimeRequestGateway(transactions)
    controller = PublicRunController(
        build_ask_agent_handler(SETTINGS),
        preparer.prepare,
    )
    return WorkflowHandler(controller.handle)


def public_stream_composer() -> WorkflowHandler:
    use_case, transactions = build_ask_agent_use_case(
        SETTINGS,
        get_http_tool_executor(),
    )
    service = AskAgentStreamService(use_case, transactions)
    preparer = PublicRuntimeRequestGateway(transactions)
    environment_guard = build_agent_runtime_environment_guard(transactions)
    controller = PublicRuntimeStreamController(
        service,
        preparer.prepare,
        environment_guard,
    )
    return WorkflowHandler(controller.handle)
