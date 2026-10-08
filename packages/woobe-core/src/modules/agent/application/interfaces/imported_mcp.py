from dataclasses import dataclass
from typing import Protocol

from modules.agent.domain.entities import Tool
from modules.agent.application.interfaces.ports import ToolSecretResolverPort
from modules.agent.application.mcp_connection_templates import ProjectEnvironmentResolver

@dataclass
class PreparedMcpInputs:
    tool: Tool
    revision: str
    secret_resolver: ToolSecretResolverPort
    environment_resolver: ProjectEnvironmentResolver


class ImportedMcpPreparationReader(Protocol):
    async def read(self, *, project_id, principal, tool_id) -> PreparedMcpInputs: ...


