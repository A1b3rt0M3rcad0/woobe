import logging
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from modules.agent.composition.composers.tool_runtime_factory import build_tool_runtime_registry
from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.dtos.tools_dtos import ExecuteToolInput
from modules.agent.application.runtime_tool_inventory import (
    execute_runtime_tool_inventory,
    is_runtime_tool_inventory_id,
)
from modules.agent.application.runtime_tool_use_cases import RuntimeExecuteToolUseCase
from modules.agent.application.tool_release_snapshots import tool_from_release_snapshot
from modules.agent.application.tool_runtime import MCP_AGENT_SESSION_INPUT_KEY
from modules.agent.application.use_cases.execution_context import current_execution
from modules.agent.composition.runtime.structured_output_ask_use_case import StructuredOutputAskAgentUseCase
from modules.agent.infra.adapters.langchain_embedding_factory import LangchainEmbeddingFactory
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.repositories import SQLAlchemyAskJobRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
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
        http_exec = HttpToolExecutor(
            allow_local_networks=settings.http_tool_allow_local_networks
        )
        job_session_id = (job.params or {}).get("session_id")

        async def read_runtime_tools(tool_ids: list[UUID]):
            async with AgentUnitOfWork(session_factory) as uow:
                tools = []
                for tool_id in tool_ids:
                    tool = await uow.tools.get_by_id(tool_id)
                    if tool is not None:
                        tools.append(tool)
                return tools

        async def execute_tool(tool_id: UUID, input_data: dict) -> dict:
            if is_runtime_tool_inventory_id(tool_id):
                return execute_runtime_tool_inventory(input_data)

            runtime_input = dict(input_data or {})
            context = current_execution.get()
            active_session_id = context.session_id if context and context.session_id else job_session_id
            if active_session_id:
                runtime_input[MCP_AGENT_SESSION_INPUT_KEY] = str(active_session_id)
            snapshot = (
                context.tool_snapshots.get(str(tool_id))
                if context and context.tool_snapshots
                else None
            )

            async with AgentUnitOfWork(session_factory) as uow:
                resolver = ToolSecretResolverAdapter(uow.tool_secrets, cipher)
                registry = build_tool_runtime_registry(
                    settings=settings,
                    executor=http_exec,
                    secret_resolver=resolver,
                )
                if snapshot is not None:
                    result = await registry.execute(
                        tool_from_release_snapshot(snapshot),
                        runtime_input,
                    )
                    return {
                        "success": result.success,
                        "output": result.output,
                        "duration_ms": result.duration_ms,
                        "error": result.error,
                    }

                uc = RuntimeExecuteToolUseCase(
                    tool_repo=uow.tools,
                    runtime_registry=registry,
                )
                result = await uc.execute(
                    ExecuteToolInput(tool_id=tool_id, input_data=runtime_input)
                )
                return result.model_dump()

        use_case = StructuredOutputAskAgentUseCase(
            session_factory=session_factory,
            llm_factory=llm_factory,
            encryption_key=settings.encryption_key,
            tool_executor_factory=execute_tool,
        )
        use_case.configure_rag_embedding_factory(LangchainEmbeddingFactory())
        use_case.configure_runtime_tool_reader(read_runtime_tools)

        started_at = time.monotonic()
        try:
            params = job.params or {}
            input_dto = AskInput(
                project_id=job.project_id,
                agent_id=job.agent_id,
                message=params.get("message", ""),
                session_id=job_session_id,
                tenant_id=params.get("tenant_id"),
                user_id=params.get("user_id"),
                metadata=params.get("metadata"),
                execution_context=params.get("execution_context", "production"),
            )
            result = await use_case.execute(input_dto)

            result_dict = result.model_dump()
            trace_id = result.trace_id
            await job_repo.mark_completed(job.id, result_dict, trace_id)
            logger.info("Job %s completed in %.2fs", job.id, time.monotonic() - started_at)
        except Exception as e:
            logger.exception("Job %s failed: %s", job.id, e)
            await job_repo.mark_failed(job.id, str(e))
