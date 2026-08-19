from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.dtos.public_runtime_dtos import PublicRunRequest
from modules.agent.application.use_cases import CreateAskJobUseCase
from modules.agent.application.use_cases.public_runtime_request_preparer import (
    PublicRuntimeRequestPreparer,
)
from modules.agent.composition.composers.ask_agent_composer import _build_ask_handler
from modules.agent.composition.runtime.ask_agent_stream_service import AskAgentStreamService
from modules.agent.composition.runtime.environment_guard import (
    build_agent_runtime_environment_guard,
)
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
from shared.infra.streaming_transactional_handler import (
    StreamingTransactionalHandler,
)
from shared.infra.transactional_handler import TransactionalHandler


def _request_preparer(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[
    [PublicRunRequest, UUID, UUID, str],
    Awaitable[PublicRunRequest],
]:
    async def prepare(
        payload: PublicRunRequest,
        project_id: UUID,
        agent_id: UUID,
        environment: str,
    ) -> PublicRunRequest:
        async with AgentUnitOfWork(session_factory) as uow:
            preparer = PublicRuntimeRequestPreparer(
                uow.releases,
                uow.sessions,
                uow.agents,
            )
            return await preparer.prepare(
                payload,
                project_id=project_id,
                agent_id=agent_id,
                environment=environment,
            )

    return prepare


def public_run_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    controller = PublicRunController(
        _build_ask_handler(session_factory),
        _request_preparer(session_factory),
    )
    return TransactionalHandler(uow, controller.handle)


def public_stream_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> StreamingTransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    service = AskAgentStreamService(
        session_factory,
        LangchainLLMFactory(),
        get_http_tool_executor(),
    )
    request_preparer = _request_preparer(session_factory)
    environment_guard = build_agent_runtime_environment_guard(session_factory)

    async def handler(request: FastAPIRequest) -> StreamingResponse:
        return await handle_public_run_stream(
            request,
            service,
            request_preparer,
            environment_guard,
        )

    return StreamingTransactionalHandler(
        uow,
        handler,
        keep_uow_open_for_stream=False,
    )


def public_create_job_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = CreateAskJobUseCase(
        uow.ask_jobs,
        SQLAlchemyAgentOutboxEventWriter(uow),
    )
    preparer = PublicRuntimeRequestPreparer(
        uow.releases,
        uow.sessions,
        uow.agents,
    )
    controller = PublicCreateJobController(use_case, preparer.prepare)
    return TransactionalHandler(uow, controller.handle)


def public_get_job_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    controller = PublicGetJobController(uow.ask_jobs)
    return TransactionalHandler(uow, controller.handle)
