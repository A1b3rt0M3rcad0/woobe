from modules.agent.composition.resources import (
    AGENT_DATABASE,
    DATABASE_ENGINE,
    SESSION_FACTORY,
    SETTINGS,
)
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.http.controllers.ask_agent_stream_controller import (
    AskAgentStreamController,
)
from modules.agent.runtime.ask_agent_stream_service import AskAgentStreamService
from modules.agent.runtime.environment_guard import (
    build_agent_runtime_environment_guard,
)
from shared.infra.streaming_transactional_handler import (
    StreamingTransactionalHandler,
)


def ask_agent_stream_composer() -> StreamingTransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    service = AskAgentStreamService(
        AGENT_DATABASE,
        SETTINGS,
        LangchainLLMFactory(),
        get_http_tool_executor(),
    )
    environment_guard = build_agent_runtime_environment_guard(SESSION_FACTORY)
    controller = AskAgentStreamController(service, environment_guard)
    return StreamingTransactionalHandler(
        uow,
        controller.handle,
        keep_uow_open_for_stream=False,
    )
