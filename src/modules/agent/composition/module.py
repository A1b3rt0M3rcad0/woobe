from __future__ import annotations

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.runtime_output_validation import EmptyModelOutputError
from modules.agent.composition.composers.public_runtime_composers import (
    public_run_composer,
    public_stream_composer,
)
from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_ask_agent_use_case,
)
from modules.agent.composition.resources import SETTINGS
from modules.agent.infra.adapters.http_tool_runtime import (
    close_http_tool_executor,
    configure_http_tool_executor,
    get_http_tool_executor,
)
from modules.agent.infra.adapters.langchain_embedding_factory import (
    LangchainEmbeddingFactory,
)
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.execution.agent_tool_runtime_gateway import AgentToolRuntimeGateway
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import (
    RuntimeStreamChannel,
    current_runtime_stream,
)
from modules.agent.infra.execution.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)
from modules.agent.presentation.http.controllers.ask_agent_stream_controller import (
    commit_safe_stream,
)
from modules.agent.presentation.http.credential_routes import router as credential_router
from modules.agent.presentation.http.mcp_tools_routes import router as mcp_tools_router
from modules.agent.presentation.http.release_activation_routes import (
    router as release_activation_router,
)
from modules.agent.presentation.http.routes import (
    agent_router,
    knowledge_router,
    router as ai_router,
    runtime_router,
    tools_router,
)
from modules.agent.presentation.http.tool_lifecycle_routes import (
    router as tool_lifecycle_router,
)
from modules.agent.presentation.http.vector_snapshot_routes import (
    router as vector_snapshot_router,
)


AGENT_HTTP_ROUTERS = (
    credential_router,
    release_activation_router,
    agent_router,
    ai_router,
    knowledge_router,
    vector_snapshot_router,
    runtime_router,
    tools_router,
    tool_lifecycle_router,
    mcp_tools_router,
)


def build_http_tool_executor() -> HttpToolExecutor:
    executor = HttpToolExecutor(
        default_timeout_ms=SETTINGS.http_tool_timeout_max_ms,
        max_timeout_ms=SETTINGS.http_tool_timeout_max_ms,
        max_response_bytes=SETTINGS.http_tool_response_max_bytes,
        allow_local_networks=SETTINGS.http_tool_allow_local_networks,
    )
    configure_http_tool_executor(executor)
    return executor


def build_agent_stream_service() -> AskAgentStreamService:
    use_case, transactions = build_ask_agent_use_case(
        SETTINGS,
        get_http_tool_executor(),
    )
    return AskAgentStreamService(use_case, transactions)


__all__ = [
    "AGENT_HTTP_ROUTERS",
    "AgentToolRuntimeGateway",
    "AskInput",
    "EmptyModelOutputError",
    "HttpToolExecutor",
    "LangchainEmbeddingFactory",
    "LangchainLLMFactory",
    "RuntimeStreamChannel",
    "SETTINGS",
    "StructuredOutputAskAgentUseCase",
    "build_agent_stream_service",
    "build_http_tool_executor",
    "close_http_tool_executor",
    "commit_safe_stream",
    "current_execution",
    "current_runtime_stream",
    "new_execution_context",
    "public_run_composer",
    "public_stream_composer",
]
