from collections.abc import Awaitable, Callable

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.composition.runtime.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.presentation.controllers.ask_agent_stream_controller import handle_ask_stream


def ask_agent_stream_composer(
    session_factory: async_sessionmaker[AsyncSession],
    executor: HttpToolExecutor | None = None,
) -> Callable[[FastAPIRequest], Awaitable[StreamingResponse]]:
    service = AskAgentStreamService(
        session_factory,
        LangchainLLMFactory(),
        executor or get_http_tool_executor(),
    )

    async def handler(fastapi_request: FastAPIRequest) -> StreamingResponse:
        return await handle_ask_stream(fastapi_request, service)

    return handler
