from __future__ import annotations

from modules.agent.application.ports import ToolExecutionPort, ToolSecretResolverPort
from modules.agent.application.tool_runtime import ToolRuntimeRegistry, build_default_tool_runtime_registry
from modules.agent.infra.adapters.redis_mcp_session_store import build_redis_mcp_session_store
from shared.infra.config import Settings


def build_tool_runtime_registry(
    *,
    settings: Settings,
    executor: ToolExecutionPort,
    secret_resolver: ToolSecretResolverPort | None = None,
) -> ToolRuntimeRegistry:
    mcp_session_store = build_redis_mcp_session_store(settings.redis_url)
    return build_default_tool_runtime_registry(
        executor,
        secret_resolver,
        mcp_session_store=mcp_session_store,
        mcp_session_ttl_seconds=settings.mcp_session_ttl_seconds,
    )
