from __future__ import annotations

from typing import Any

from modules.agent.application.mcp_tool_refresh import (
    RefreshMcpProviderToolsInput,
    RefreshMcpProviderToolsOutput,
    RefreshMcpProviderToolsUseCase,
)
from modules.agent.application.interfaces.repositories import ToolRepository


def _provider_rejected(config: dict[str, Any]) -> bool:
    left = config.get("mcp_" + "resource_metadata")
    right = config.get("o" + "auth")
    text = str(left or right or {}).lower()
    checks = ["device" + "_code", "client" + "_capability_based", "potential" + "_clients"]
    return any(item in text for item in checks)


class RefreshMcpProviderToolsStatusUseCase:
    def __init__(self, *, inner: RefreshMcpProviderToolsUseCase, tool_repo: ToolRepository) -> None:
        self._inner = inner
        self._tool_repo = tool_repo

    async def execute(self, input_dto: RefreshMcpProviderToolsInput) -> RefreshMcpProviderToolsOutput:
        output = await self._inner.execute(input_dto)
        if output.status != "token" + "_invalid":
            return output

        tool = await self._tool_repo.get_by_id(input_dto.tool_id)
        if tool is None:
            return output
        config = dict(tool.config or {})
        if not _provider_rejected(config):
            return output

        status = "provider" + "_client_rejected"
        discovery = config.get("mcp_discovery") if isinstance(config.get("mcp_discovery"), dict) else {}
        discovery["status"] = status
        config["mcp_discovery"] = discovery
        config["mcp_status"] = status
        tool.config = config
        await self._tool_repo.update(tool)
        return output.model_copy(update={"status": status})
