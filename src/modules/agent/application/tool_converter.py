from __future__ import annotations

from modules.agent.application.tool_runtime import build_default_tool_runtime_registry


class _DefinitionOnlyExecutor:
    async def execute(self, *args, **kwargs):  # pragma: no cover - never called by definition building
        raise RuntimeError("Definition-only executor cannot run tools")


def agent_tool_to_openai_definition(tool) -> dict:
    registry = build_default_tool_runtime_registry(_DefinitionOnlyExecutor())
    return registry.to_openai_definition(tool)


def agent_tools_to_openai_definitions(tools: list) -> list[dict]:
    return [agent_tool_to_openai_definition(t) for t in tools]


def _safe_tool_name(tool) -> str:
    name = tool.name.lower().strip().replace(" ", "_").replace("-", "_")
    name = "".join(c for c in name if c.isalnum() or c == "_")
    if not name or name[0].isdigit():
        name = f"tool_{name}"
    return name
