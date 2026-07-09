from collections.abc import Awaitable, Callable

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.composers.ask_agent_composer import ask_agent_composer
from modules.agent.application.use_cases import CreateAskJobUseCase
from modules.agent.application.use_cases.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.public_runtime_controllers import (
    PublicCreateJobController,
    PublicGetJobController,
    PublicRunController,
)
from modules.agent.presentation.controllers.public_runtime_stream_controller import (
    handle_public_run_stream,
)
from shared.infra.transactional_handler import TransactionalHandler


def public_run_composer(session_factory: async_sessionmaker[AsyncSession]):
    internal_handler = ask_agent_composer(session_factory)
    return PublicRunController(internal_handler).handle


def public_stream_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[FastAPIRequest], Awaitable[StreamingResponse]]:
    service = AskAgentStreamService(
        session_factory,
        LangchainLLMFactory(),
        get_http_tool_executor(),
    )

    async def handler(request: FastAPIRequest) -> StreamingResponse:
        return await handle_public_run_stream(request, service)

    return handler


def public_create_job_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = CreateAskJobUseCase(
        uow.ask_jobs,
        SQLAlchemyAgentOutboxEventWriter(uow),
    )
    controller = PublicCreateJobController(use_case)
    return TransactionalHandler(uow, controller.handle)


def public_get_job_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    controller = PublicGetJobController(uow.ask_jobs)
    return TransactionalHandler(uow, controller.handle)
