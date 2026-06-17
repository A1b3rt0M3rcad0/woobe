from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.dtos.tools_dtos import ExecuteToolInput
from modules.agent.application.use_cases.structured_output_ask_use_case import StructuredOutputAskAgentUseCase
from modules.agent.application.use_cases.tools_use_cases import ExecuteToolUseCase
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.ask_agent_controller import AskAgentController
from shared.infra.config import Settings


_http_executor = None


def _get_http_executor():
    global _http_executor
    if _http_executor is None:
        _http_executor = HttpToolExecutor()
    return _http_executor


async def close_ask_agent_resources():
    global _http_executor
    if _http_executor is not None:
        await _http_executor.aclose()
        _http_executor = None


def ask_agent_composer(session_factory: async_sessionmaker[AsyncSession]):
    settings = Settings()
    llm_factory = LangchainLLMFactory()
    cipher = SecretCipherAdapter(settings.encryption_key)

    async def execute_tool(tool_id: UUID, input_data: dict) -> dict:
        async with AgentUnitOfWork(session_factory) as uow:
            resolver = ToolSecretResolverAdapter(uow.tool_secrets, cipher)
            use_case = ExecuteToolUseCase(
                tool_repo=uow.tools,
                tool_executor=_get_http_executor(),
                secret_resolver=resolver,
            )
            result = await use_case.execute(
                ExecuteToolInput(tool_id=tool_id, input_data=input_data)
            )
            return result.model_dump()

    use_case = StructuredOutputAskAgentUseCase(
        session_factory=session_factory,
        llm_factory=llm_factory,
        encryption_key=settings.encryption_key,
        tool_executor_factory=execute_tool,
    )
    return AskAgentController(use_case).handle
