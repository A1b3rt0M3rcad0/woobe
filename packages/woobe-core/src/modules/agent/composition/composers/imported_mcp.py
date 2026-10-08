from modules.agent.application.imported_mcp import PrepareImportedMcpUseCase
from modules.agent.application.mcp_oauth import McpOAuthConfigTokenProvider
from modules.agent.composition.resources import SETTINGS
from modules.agent.composition.factories.agent_uow_factory import build_agent_read_uow
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.database.imported_mcp_reader import (
    SQLAlchemyImportedMcpPreparationReader,
)


def build_imported_mcp_preparation() -> PrepareImportedMcpUseCase:
    executor = get_http_tool_executor()
    reader = SQLAlchemyImportedMcpPreparationReader(
        build_agent_read_uow, encryption_key=SETTINGS.encryption_key
    )
    oauth = McpOAuthConfigTokenProvider(
        executor=executor, cipher=SecretCipherAdapter(SETTINGS.encryption_key)
    )
    return PrepareImportedMcpUseCase(reader, executor, oauth)
