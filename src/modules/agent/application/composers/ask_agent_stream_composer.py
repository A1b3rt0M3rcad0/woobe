from collections.abc import Callable

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.runtime.presentation.controllers.ask_agent_stream_controller import (
    handle_ask_stream,
)
from modules.agent.application.use_cases.ask_agent_stream_service import AskAgentStreamService


def ask_agent_stream_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[FastAPIRequest], StreamingResponse]:
    service = AskAgentStreamService(session_factory)

    async def handler(fastapi_request: FastAPIRequest) -> StreamingResponse:
        return await handle_ask_stream(fastapi_request, service)

    return handler
