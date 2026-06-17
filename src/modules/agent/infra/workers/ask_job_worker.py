import logging
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from modules.agent.application.dtos.tools_dtos import ExecuteToolInput
from modules.agent.application.use_cases.tools_use_cases import ExecuteToolUseCase
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.repositories import (
    SQLAlchemyAskJobRepository,
)
from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase
from modules.agent.application.dtos.runtime_dtos import AskInput
from shared.infra.config import Settings

logger = logging.getLogger(__name__)


class AskJobWorker:

    def __init__(self, async_engine: AsyncEngine) -> None:
        self._engine = async_engine

    async def run(self) -> None:
        session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        async with session_factory() as session:
            job_repo = SQLAlchemyAskJobRepository(session)
            pending = await job_repo.list_pending(limit=5)
            for job in pending:
                try:
                    await self._process_job(session_factory, job_repo, job)
                except Exception as e:
                    logger.exception("Failed to process job %s: %s", job.id, e)
                    await job_repo.mark_failed(job.id, str(e))

    async def _process_job(
        self,
        session_factory: async_sessionmaker,
        job_repo: SQLAlchemyAskJobRepository,
        job: object,
    ) -> None:
        from modules.agent.domain.entities import AskJob
        if not isinstance(job, AskJob):
            return

        await job_repo.mark_started(job.id)

        llm_factory = LangchainLLMFactory()
        settings = Settings()
        cipher = SecretCipherAdapter(settings.encryption_key)
        http_exec = HttpToolExecutor()

        async def execute_tool(tool_id: UUID, input_data: dict) -> dict:
            async with AgentUnitOfWork(session_factory) as uow:
                resolver = ToolSecretResolverAdapter(uow.tool_secrets, cipher)
                uc = ExecuteToolUseCase(
                    tool_repo=uow.tools,
                    tool_executor=http_exec,
                    secret_resolver=resolver,
                )
                result = await uc.execute(
                    ExecuteToolInput(tool_id=tool_id, input_data=input_data)
                )
                return result.model_dump()

        use_case = AskAgentUseCase(
            session_factory=session_factory,
            llm_factory=llm_factory,
            encryption_key=settings.encryption_key,
            tool_executor_factory=execute_tool,
        )

        started_at = time.monotonic()
        try:
            input_dto = AskInput(
                project_id=job.project_id,
                agent_id=job.agent_id,
                message=(job.params or {}).get("message", ""),
                session_id=(job.params or {}).get("session_id"),
            )
            result = await use_case.execute(input_dto)

            result_dict = result.model_dump()
            trace_id = result.trace_id
            await job_repo.mark_completed(job.id, result_dict, trace_id)
            logger.info("Job %s completed in %.2fs", job.id, time.monotonic() - started_at)
        except Exception as e:
            logger.exception("Job %s failed: %s", job.id, e)
            await job_repo.mark_failed(job.id, str(e))
