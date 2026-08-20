import logging
import time

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.composition.runtime.agent_tool_runtime_gateway import (
    AgentToolRuntimeGateway,
)
from modules.agent.composition.runtime.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)
from modules.agent.domain.entities import AskJob
from modules.agent.infra.adapters.langchain_embedding_factory import LangchainEmbeddingFactory
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.database import AgentDatabase, agent_session_factory
from modules.agent.infra.database.repositories import SQLAlchemyAskJobRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.config import Settings

logger = logging.getLogger(__name__)


class AskJobWorker:
    def __init__(self, async_engine: AsyncEngine) -> None:
        self._engine = async_engine

    async def run(self) -> None:
        session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        database = AgentDatabase(session_factory)

        async with AgentUnitOfWork(database) as uow:
            pending = await SQLAlchemyAskJobRepository(uow).list_pending(limit=5)

        for job in pending:
            try:
                await self._process_job(database, job)
            except Exception as exc:
                logger.exception("Failed to process job %s: %s", job.id, exc)
                async with AgentUnitOfWork(database) as uow:
                    await SQLAlchemyAskJobRepository(uow).mark_failed(job.id, str(exc))

    async def _process_job(
        self,
        database: AgentDatabase,
        job: AskJob,
    ) -> None:
        async with AgentUnitOfWork(database) as uow:
            await SQLAlchemyAskJobRepository(uow).mark_started(job.id)

        settings = Settings()
        http_executor = HttpToolExecutor(
            allow_local_networks=settings.http_tool_allow_local_networks
        )
        tool_runtime = AgentToolRuntimeGateway(database, settings, http_executor)
        use_case = StructuredOutputAskAgentUseCase(
            session_factory=agent_session_factory(database),
            llm_factory=LangchainLLMFactory(),
            encryption_key=settings.encryption_key,
            tool_executor_factory=tool_runtime.execute_tool,
        )
        use_case.configure_rag_embedding_factory(LangchainEmbeddingFactory())
        use_case.configure_runtime_tool_reader(tool_runtime.read_runtime_tools)

        params = job.params or {}
        input_dto = AskInput(
            project_id=job.project_id,
            agent_id=job.agent_id,
            message=params.get("message", ""),
            session_id=params.get("session_id"),
            tenant_id=params.get("tenant_id"),
            user_id=params.get("user_id"),
            metadata=params.get("metadata"),
            execution_context=params.get("execution_context", "production"),
        )

        started_at = time.monotonic()
        try:
            result = await use_case.execute(input_dto)
        except Exception as exc:
            logger.exception("Job %s failed: %s", job.id, exc)
            async with AgentUnitOfWork(database) as uow:
                await SQLAlchemyAskJobRepository(uow).mark_failed(job.id, str(exc))
            return

        async with AgentUnitOfWork(database) as uow:
            await SQLAlchemyAskJobRepository(uow).mark_completed(
                job.id,
                result.model_dump(),
                result.trace_id,
            )
        logger.info("Job %s completed in %.2fs", job.id, time.monotonic() - started_at)
