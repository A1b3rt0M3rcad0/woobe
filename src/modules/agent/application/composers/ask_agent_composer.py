from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.presentation.controllers.ask_agent_controller import (
    AskAgentController,
)
from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase
from shared.infra.config import Settings


def ask_agent_composer(session_factory: async_sessionmaker[AsyncSession]):
    settings = Settings()
    llm_factory = LangchainLLMFactory()

    use_case = AskAgentUseCase(
        session_factory=session_factory,
        llm_factory=llm_factory,
        encryption_key=settings.encryption_key,
    )

    controller = AskAgentController(use_case)
    return controller.handle
