from copy import deepcopy
from modules.agent.application.interfaces.imported_mcp import (
    ImportedMcpPreparationReader,
)

from modules.agent.application.interfaces.ports import (
    ToolExecutionPort,
)
from modules.agent.application.mcp_tool_refresh import discover_mcp_tool_definition
from modules.agent.domain.imported_dependencies import ImportedDependencyPending
from shared.contracts.time import utc_now
from shared.contracts.errors import ValidationError


class PrepareImportedMcpUseCase:
    def __init__(
        self,
        reader: ImportedMcpPreparationReader,
        executor: ToolExecutionPort,
        auth_header_provider,
    ):
        self._reader, self._executor, self._oauth = (
            reader,
            executor,
            auth_header_provider,
        )

    async def execute(
        self,
        *,
        project_id,
        principal,
        tool_id,
        desired_permissions,
        require_ready=False,
    ):
        prepared = await self._reader.read(
            project_id=project_id, principal=principal, tool_id=tool_id
        )
        tool = prepared.tool
        if (
            require_ready
            and tool.config.get("mcp_status") == "oauth_required"
            and (tool.config.get("oauth") or {}).get("status") != "connected"
        ):
            raise ImportedDependencyPending(
                [{"kind": "McpOAuth", "id": str(tool_id), "code": "MCP_OAUTH_REQUIRED"}]
            )
        result = await discover_mcp_tool_definition(
            tool=tool,
            executor=self._executor,
            secret_resolver=prepared.secret_resolver,
            auth_header_provider=self._oauth,
            project_environment_resolver=prepared.environment_resolver,
            timeout_ms=tool.timeout_ms or 10000,
            now=utc_now(),
        )
        if result.status == "oauth_required" and require_ready:
            raise ImportedDependencyPending(
                [{"kind": "McpOAuth", "id": str(tool_id), "code": "MCP_OAUTH_REQUIRED"}]
            )
        if result.status not in {"ready", "oauth_required"}:
            raise ValidationError("Imported MCP discovery failed")
        if result.status == "ready":
            names = {item["name"] for item in tool.config.get("discovered_tools", [])}
            if len(names) != len(tool.config.get("discovered_tools", [])):
                raise ValidationError(
                    "Fresh MCP discovery contains ambiguous remote Tool names"
                )
            requested = {
                item["remote_name"]: {
                    "mode": item["permission"],
                    **(
                        {"risk_level": item["risk"]}
                        if item.get("risk") is not None
                        else {}
                    ),
                }
                for item in desired_permissions
            }
            if len(requested) != len(desired_permissions) or set(requested) - names:
                raise ValidationError(
                    "Declared MCP permissions do not match fresh remote Tools"
                )
            selected = tool.config.get("tool_name")
            if selected and selected not in names:
                raise ValidationError(
                    "Selected MCP Tool is absent from fresh discovery"
                )
            if selected and tool.config.get("mode", "tool") == "tool":
                requested.setdefault(
                    selected,
                    {
                        "mode": (tool.config.get("permission") or {}).get(
                            "mode", "allow"
                        )
                    },
                )
            author_bindings = {
                item["remote_name"]: item.get("bindings", {})
                for item in desired_permissions
            }
            for item in tool.config.get("discovered_tools", []):
                if item["name"] in author_bindings:
                    item["bindings"] = deepcopy(author_bindings[item["name"]])
                item["permission"] = requested.get(item["name"], {"mode": "review"})
        return {
            "project_id": str(project_id),
            "tool_id": str(tool.id),
            "expected_revision": prepared.revision,
            "config": tool.config,
            "status": result.status,
            "discovered_count": result.discovered_count,
            "require_ready": require_ready,
        }
