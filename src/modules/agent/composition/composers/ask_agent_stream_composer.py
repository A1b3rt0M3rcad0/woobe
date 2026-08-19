from collections.abc import Awaitable, Callable

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.composition.runtime.ask_agent_stream_service import AskAgentStreamService
from modules.agent.composition.runtime.environment_guard import (
    build_agent_runtime_environment_guard,
)
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.ask_agent_stream_controller import (
    handle_ask_stream,
)
from shared.infra.streaming_transactional_handler import (
    StreamingTransactionalHandler,
)


AskStreamHttpHandler = Callable[[FastAPIRequest], Awaitable[StreamingResponse]]


def _build_ask_stream_handler(
    session_factory: async_sessionmaker[AsyncSession],
    executor: HttpToolExecutor | None = None,
) -> AskStreamHttpHandler:
    service = AskAgentStreamService(
        session_factory,
        LangchainLLMFactory(),
        executor or get_http_tool_executor(),
    )
    environment_guard = build_agent_runtime_environment_guard(session_factory)

    async def handler(fastapi_request: FastAPIRequest) -> StreamingResponse:
        return await handle_ask_stream(
            fastapi_request,
            service,
            environment_guard,
        )

    return handler


def ask_agent_stream_composer(
    session_factory: async_sessionmaker[AsyncSession],
    executor: HttpToolExecutor | None = None,
) -> StreamingTransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    return StreamingTransactionalHandler(
        uow,
        _build_ask_stream_handler(session_factory, executor),
        keep_uow_open_for_stream=False,
    )
