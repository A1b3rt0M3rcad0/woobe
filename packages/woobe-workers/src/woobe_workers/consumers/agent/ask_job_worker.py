import logging
import time

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.background_boundary import AskInput
from modules.agent.background_boundary import AskJob
from modules.agent.background_boundary import LangchainLLMFactory
from modules.agent.background_boundary import HttpToolExecutor
from modules.agent.background_boundary import SQLAlchemyAskJobRepository
from modules.agent.background_boundary import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.background_boundary import AgentUnitOfWork
from modules.agent.background_boundary import AgentToolRuntimeGateway
from modules.agent.background_boundary import build_execution_strategy_resolver
from modules.agent.background_boundary import build_runtime_context_manager
from modules.agent.background_boundary import (
    TransactionBoundedStructuredOutputRuntime,
)
from modules.agent.entrypoint import build_rag_runtime_adapter
from woobe_workers.settings import WorkerSettings

logger = logging.getLogger(__name__)


class AskJobWorker:
    def __init__(self, async_engine: AsyncEngine, settings: WorkerSettings) -> None:
        self._engine = async_engine
        self._settings = settings

    def _transactions(self) -> AgentRuntimeTransactionRunner:
        return AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(self._engine))

    async def run(self) -> None:
        async with AgentUnitOfWork(self._engine) as uow:
            pending = await SQLAlchemyAskJobRepository(uow).list_pending(limit=5)

        for job in pending:
            try:
                await self._process_job(job)
            except Exception as exc:
                logger.exception("Failed to process job %s: %s", job.id, exc)
                async with AgentUnitOfWork(self._engine) as uow:
                    await SQLAlchemyAskJobRepository(uow).mark_failed(job.id, str(exc))

    async def _process_job(self, job: AskJob) -> None:
        async with AgentUnitOfWork(self._engine) as uow:
            await SQLAlchemyAskJobRepository(uow).mark_started(job.id)

        settings = self._settings
        transactions = self._transactions()
        http_executor = HttpToolExecutor(
            allow_local_networks=settings.http_tool_allow_local_networks
        )
        tool_runtime = AgentToolRuntimeGateway(
            transactions,
            settings,
            http_executor,
        )
        execution = TransactionBoundedStructuredOutputRuntime(
            transactions=transactions,
            llm_factory=LangchainLLMFactory(),
            encryption_key=settings.encryption_key,
            tool_executor_factory=tool_runtime.execute_tool,
        )
        execution.configure_context_manager(
            build_runtime_context_manager(settings.default_context_manager)
        )
        execution.configure_execution_strategy_resolver(
            build_execution_strategy_resolver()
        )
        execution.configure_rag_runtime(
            build_rag_runtime_adapter(
                transactions,
                encryption_key=settings.encryption_key,
            )
        )
        execution.configure_runtime_tool_reader(tool_runtime.read_runtime_tools)

        params = job.params or {}
        input_dto = AskInput(
            project_id=job.project_id,
            agent_id=job.agent_id,
            message=params.get("message", ""),
            session_id=params.get("session_id"),
            tenant_id=params.get("tenant_id"),
            user_id=params.get("user_id"),
            metadata=params.get("metadata"),
            external_context=params.get("external_context"),
            execution_context=params.get("execution_context", "production"),
        )

        started_at = time.monotonic()
        try:
            result = await execution.execute(input_dto)
        except Exception as exc:
            logger.exception("Job %s failed: %s", job.id, exc)
            async with AgentUnitOfWork(self._engine) as uow:
                await SQLAlchemyAskJobRepository(uow).mark_failed(job.id, str(exc))
            return

        async with AgentUnitOfWork(self._engine) as uow:
            repository = SQLAlchemyAskJobRepository(uow)
            if result.status == "waiting":
                await repository.mark_waiting(
                    job.id,
                    result.model_dump(),
                    result.trace_id,
                )
                logger.info(
                    "Job %s is waiting after %.2fs",
                    job.id,
                    time.monotonic() - started_at,
                )
                return
            await repository.mark_completed(
                job.id,
                result.model_dump(),
                result.trace_id,
            )
        logger.info("Job %s completed in %.2fs", job.id, time.monotonic() - started_at)
