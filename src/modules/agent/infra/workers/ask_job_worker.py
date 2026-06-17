import logging
import time

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from modules.agent.infra.database.repositories import (
    SQLAlchemyAskJobRepository,
)
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
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

        use_case = AskAgentUseCase(
            session_factory=session_factory,
            llm_factory=llm_factory,
            encryption_key=settings.encryption_key,
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
