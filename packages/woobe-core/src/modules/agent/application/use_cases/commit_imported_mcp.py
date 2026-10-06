from modules.agent.application.interfaces.repositories import ToolRepository
from modules.agent.application.mcp_permissions import write_mcp_readiness
from shared.contracts.errors import ConflictError, NotFoundError


class CommitImportedMcpUseCase:
    def __init__(self, tools: ToolRepository):
        self._tools = tools

    async def execute(self, definition):
        tool = await self._tools.lock_by_id(definition.tool_id)
        if tool.project_id != definition.project_id:
            raise NotFoundError("Imported MCP Tool is unavailable")
        if tool.updated_at.isoformat() != definition.expected_revision:
            raise ConflictError("Imported MCP Tool changed during discovery")
        if definition.require_ready and definition.status != "ready":
            raise ConflictError("Imported MCP Tool has not completed fresh discovery")
        tool.config = definition.config
        if tool.config.get("input_schema_source") == "discovered" and tool.config.get(
            "tool_name"
        ):
            remote = next(
                (
                    item
                    for item in tool.config.get("discovered_tools", [])
                    if item["name"] == tool.config["tool_name"]
                ),
                None,
            )
            if remote:
                tool.input_schema = remote.get("input_schema") or {}
                tool.config["discovered_input_schema"] = tool.input_schema
        write_mcp_readiness(tool.config)
        await self._tools.update(tool)
        return {
            "id": str(tool.id),
            "status": definition.status,
            "discovered_count": definition.discovered_count,
            "fresh_discovery": True,
            "readiness": tool.config["mcp_readiness"]["state"],
        }
