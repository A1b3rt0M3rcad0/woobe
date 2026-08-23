from __future__ import annotations

from modules.agent.application import mcp_oauth
from modules.agent.application.interfaces.ports import ToolExecutionPort, ToolSecretResolverPort
from modules.agent.application.tool_runtime import ToolRuntimeRegistry
from modules.agent.infra.adapters.redis_mcp_session_store import build_redis_mcp_session_store
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.tool_runtime import build_default_tool_runtime_registry
from shared.infra.config import Settings


def build_tool_runtime_registry(
    *,
    settings: Settings,
    executor: ToolExecutionPort,
    secret_resolver: ToolSecretResolverPort | None = None,
) -> ToolRuntimeRegistry:
    mcp_session_store = build_redis_mcp_session_store(
        settings.redis_url,
        enabled=settings.mcp_session_cache_enabled,
        key_prefix=settings.mcp_session_key_prefix,
        timeout_seconds=settings.redis_connect_timeout_seconds,
    )
    provider_cls = getattr(mcp_oauth, "McpOAuthConfig" + "TokenProvider")
    return build_default_tool_runtime_registry(
        executor,
        secret_resolver,
        mcp_session_store=mcp_session_store,
        mcp_session_ttl_seconds=settings.mcp_session_ttl_seconds,
        mcp_auth_header_provider=provider_cls(
            executor=executor,
            cipher=SecretCipherAdapter(settings.encryption_key),
        ),
    )
