from __future__ import annotations

from typing import Any
from starlette.routing import compile_path
from shared.security.control_plane import CATALOG_REVISION

# Explicitly reviewed method/template pairs. Never derive authority from a prefix.
_REVIEWED = [
    (
        "GET",
        "/identity/workspaces/{workspace_id}/authority-categories",
        "categories:read",
    ),
    (
        "POST",
        "/identity/workspaces/{workspace_id}/authority-categories",
        "categories:create",
    ),
    (
        "GET",
        "/identity/workspaces/{workspace_id}/authority-categories/{category_id}",
        "categories:read",
    ),
    (
        "PATCH",
        "/identity/workspaces/{workspace_id}/authority-categories/{category_id}",
        "categories:update",
    ),
    (
        "POST",
        "/identity/workspaces/{workspace_id}/authority-categories/{category_id}/clone",
        "categories:create",
    ),
    (
        "GET",
        "/identity/workspaces/{workspace_id}/authority-categories/{category_id}/versions",
        "categories:read",
    ),
    (
        "POST",
        "/identity/workspaces/{workspace_id}/authority-categories/{category_id}/archive",
        "categories:archive",
    ),
    (
        "DELETE",
        "/identity/workspaces/{workspace_id}/authority-categories/{category_id}",
        "categories:delete",
    ),
    ("GET", "/core/workspaces/{workspace_id}/control-keys", "keys:read"),
    ("POST", "/core/workspaces/{workspace_id}/control-keys", "keys:create"),
    (
        "PATCH",
        "/core/workspaces/{workspace_id}/control-keys/{control_key_id}",
        "keys:update",
    ),
    (
        "POST",
        "/core/workspaces/{workspace_id}/control-keys/{control_key_id}/revoke",
        "keys:revoke",
    ),
    (
        "POST",
        "/core/workspaces/{workspace_id}/control-keys/{control_key_id}/rotate",
        "keys:rotate",
    ),
    ("GET", "/core/projects", "workspace:read"),
    ("POST", "/core/projects", "projects:create"),
    ("GET", "/core/projects/{access_project_id}/members", "project:access:read"),
    ("POST", "/core/projects/{access_project_id}/access", "project:access:write"),
    (
        "DELETE",
        "/core/projects/{access_project_id}/access/{subject_type}/{subject_id}",
        "project:access:write",
    ),
    ("POST", "/core/projects/{access_project_id}/members", "project:access:write"),
    (
        "DELETE",
        "/core/projects/{access_project_id}/members/{target_user_id}",
        "project:access:write",
    ),
    ("GET", "/core/projects/{project_id}/overview", "project:read"),
    ("GET", "/core/projects/{project_id}/runs", "project:read"),
    ("GET", "/core/projects/{project_id}", "project:read"),
    ("PATCH", "/core/projects/{project_id}", "project:update"),
    ("GET", "/core/projects/{project_id}/environment-keys", "project:environment:read"),
    (
        "PUT",
        "/core/projects/{project_id}/environment-keys/{key}",
        "project:environment:write",
    ),
    (
        "DELETE",
        "/core/projects/{project_id}/environment-keys/{key}",
        "project:environment:write",
    ),
    ("POST", "/core/projects/{project_id}/api-keys", "api_key:write"),
    ("POST", "/core/projects/{project_id}/runtime-keys", "api_key:write"),
    ("GET", "/core/projects/{project_id}/api-keys", "api_key:read"),
    (
        "POST",
        "/core/projects/{project_id}/api-keys/{api_key_id}/revoke",
        "api_key:write",
    ),
    (
        "POST",
        "/core/projects/{project_id}/api-keys/{api_key_id}/rotate",
        "api_key:write",
    ),
    ("PATCH", "/core/projects/{project_id}/api-keys/{api_key_id}", "api_key:write"),
    ("POST", "/chat-surfaces/projects/{project_id}", "chat_surface:write"),
    ("GET", "/chat-surfaces/projects/{project_id}", "chat_surface:read"),
    ("GET", "/chat-surfaces/{surface_id}", "chat_surface:read"),
    ("PATCH", "/chat-surfaces/{surface_id}", "chat_surface:write"),
    ("POST", "/chat-surfaces/{surface_id}/release", "chat_surface:release"),
    ("POST", "/chat-surfaces/{surface_id}/activate", "chat_surface:write"),
    ("POST", "/chat-surfaces/{surface_id}/disable", "chat_surface:write"),
    ("POST", "/chat-surfaces/{surface_id}/archive", "chat_surface:write"),
    ("POST", "/chat-surfaces/{surface_id}/access-keys", "chat_surface:keys"),
    ("GET", "/chat-surfaces/{surface_id}/access-keys", "chat_surface:keys"),
    (
        "POST",
        "/chat-surfaces/{surface_id}/access-keys/{api_key_id}/rotate",
        "chat_surface:keys",
    ),
    (
        "POST",
        "/chat-surfaces/{surface_id}/access-keys/{api_key_id}/revoke",
        "chat_surface:keys",
    ),
    ("GET", "/chat-surfaces/{surface_id}/sessions", "chat_surface:read"),
    ("GET", "/chat-surfaces/{surface_id}/activity", "chat_surface:read"),
    ("POST", "/chat-surfaces/{surface_id}/test-sessions", "chat_surface:write"),
    ("GET", "/ai/projects/{project_id}/skills", "skill:read"),
    ("POST", "/ai/projects/{project_id}/skills", "skill:write"),
    (
        "GET",
        "/ai/projects/{project_id}/skills/versions/{skill_version_id}",
        "skill:read",
    ),
    ("GET", "/ai/projects/{project_id}/skills/{skill_id}/versions", "skill:read"),
    ("POST", "/ai/projects/{project_id}/skills/{skill_id}/versions", "skill:version"),
    ("POST", "/ai/credentials/{credential_id}/rotate", "provider:credential:rotate"),
    ("GET", "/ai/credentials/{credential_id}/usage", "provider:read"),
    ("DELETE", "/ai/credentials/{credential_id}", "provider:delete"),
    ("POST", "/ai/credentials/{credential_id}/revoke", "provider:credential:revoke"),
    ("DELETE", "/ai/provider-models/{provider_model_id}", "model:delete"),
    ("GET", "/ai/provider-models/{provider_model_id}/usage", "model:read"),
    ("GET", "/ai/agents/{agent_id}/release-activations", "agent:read"),
    ("GET", "/agent/knowledge/collections", "knowledge:read"),
    ("POST", "/agent/knowledge/collections", "knowledge:write"),
    ("GET", "/agent/knowledge/collections/{collection_id}", "knowledge:read"),
    ("PATCH", "/agent/knowledge/collections/{collection_id}", "knowledge:write"),
    ("DELETE", "/agent/knowledge/collections/{collection_id}", "knowledge:delete"),
    ("GET", "/agent/knowledge/agent-collections", "knowledge:read"),
    ("POST", "/agent/knowledge/agent-collections", "knowledge:write"),
    ("DELETE", "/agent/knowledge/agent-collections/{link_id}", "knowledge:delete"),
    ("GET", "/agent/knowledge/documents", "knowledge:read"),
    ("POST", "/agent/knowledge/documents", "knowledge:write"),
    ("POST", "/agent/knowledge/documents/upload", "knowledge:write"),
    ("DELETE", "/agent/knowledge/documents/{document_id}", "knowledge:delete"),
    ("GET", "/agent/knowledge/documents/{document_id}", "knowledge:read"),
    ("POST", "/agent/knowledge/search", "knowledge:write"),
    (
        "POST",
        "/agent/knowledge/agents/{agent_id}/knowledge-versions",
        "knowledge:write",
    ),
    ("GET", "/agent/knowledge/agents/{agent_id}/knowledge-versions", "knowledge:read"),
    ("POST", "/ai/credentials", "provider:write"),
    ("PATCH", "/ai/credentials/{credential_id}", "provider:write"),
    ("GET", "/ai/credentials", "provider:read"),
    ("POST", "/ai/provider-models", "model:write"),
    ("GET", "/ai/provider-models", "model:read"),
    ("GET", "/ai/provider-models/{provider_model_id}", "model:read"),
    ("PATCH", "/ai/provider-models/{provider_model_id}", "model:write"),
    ("POST", "/ai/agents", "agent:write"),
    ("GET", "/ai/agents", "agent:read"),
    ("GET", "/ai/agents/{agent_id}", "agent:read"),
    ("PATCH", "/ai/agents/{agent_id}", "agent:write"),
    ("DELETE", "/ai/agents/{agent_id}", "agent:delete"),
    ("POST", "/ai/agents/{agent_id}/prompts", "agent:write"),
    ("GET", "/ai/agents/{agent_id}/prompts", "agent:read"),
    ("GET", "/ai/agents/{agent_id}/prompts/{version_id}", "agent:read"),
    ("POST", "/ai/agents/{agent_id}/contracts", "agent:write"),
    ("PATCH", "/ai/agents/{agent_id}/contracts/{contract_id}", "agent:write"),
    ("GET", "/ai/agents/{agent_id}/contracts", "agent:read"),
    ("GET", "/ai/agents/{agent_id}/contracts/{contract_id}", "agent:read"),
    ("POST", "/ai/agents/{agent_id}/model-configs", "agent:write"),
    ("GET", "/ai/agents/{agent_id}/model-configs", "agent:read"),
    ("GET", "/ai/agents/{agent_id}/model-configs/{config_id}", "agent:read"),
    ("POST", "/ai/agents/{agent_id}/releases", "agent:version"),
    ("GET", "/ai/agents/{agent_id}/releases", "agent:read"),
    ("GET", "/ai/agents/{agent_id}/releases/{release_id}", "agent:read"),
    ("POST", "/ai/agents/{agent_id}/releases/{release_id}/promote", "agent:production"),
    (
        "POST",
        "/ai/agents/{agent_id}/releases/{release_id}/rollback",
        "agent:production",
    ),
    ("DELETE", "/ai/agents/{agent_id}/releases/{release_id}", "agent:version"),
    ("POST", "/ai/agents/{agent_id}/release-tests", "agent:version"),
    ("GET", "/ai/agents/{agent_id}/releases/{release_id}/tests", "agent:read"),
    ("GET", "/knowledge/collections", "knowledge:read"),
    ("POST", "/knowledge/collections", "knowledge:write"),
    ("GET", "/knowledge/collections/{collection_id}", "knowledge:read"),
    ("PATCH", "/knowledge/collections/{collection_id}", "knowledge:write"),
    ("DELETE", "/knowledge/collections/{collection_id}", "knowledge:delete"),
    ("GET", "/knowledge/agent-collections", "knowledge:read"),
    ("POST", "/knowledge/agent-collections", "knowledge:write"),
    ("DELETE", "/knowledge/agent-collections/{link_id}", "knowledge:delete"),
    ("GET", "/knowledge/documents", "knowledge:read"),
    ("POST", "/knowledge/documents", "knowledge:write"),
    ("POST", "/knowledge/documents/upload", "knowledge:write"),
    ("DELETE", "/knowledge/documents/{document_id}", "knowledge:delete"),
    ("GET", "/knowledge/documents/{document_id}", "knowledge:read"),
    ("POST", "/knowledge/search", "knowledge:read"),
    ("POST", "/knowledge/agents/{agent_id}/knowledge-versions", "knowledge:write"),
    ("GET", "/knowledge/agents/{agent_id}/knowledge-versions", "knowledge:read"),
    ("GET", "/agent/knowledge/collections/{collection_id}/overview", "knowledge:read"),
    (
        "POST",
        "/agent/knowledge/collections/{collection_id}/vector-preview",
        "knowledge:read",
    ),
    (
        "POST",
        "/agent/knowledge/collections/{collection_id}/vector-snapshots",
        "knowledge:write",
    ),
    (
        "GET",
        "/agent/knowledge/collections/{collection_id}/vector-snapshots",
        "knowledge:read",
    ),
    ("GET", "/agent/knowledge/vector-snapshots/{snapshot_id}", "knowledge:read"),
    ("GET", "/runtime/runs", "run:read"),
    ("GET", "/runtime/runs/by-trace/{trace_id}/model-invocations", "run:read"),
    ("GET", "/runtime/runs/by-trace/{trace_id}", "run:read"),
    ("GET", "/runtime/runs/{run_id}/model-invocations", "run:read"),
    ("GET", "/runtime/runs/{run_id}", "run:read"),
    ("GET", "/tools/tools", "tool:read"),
    ("POST", "/tools/tools", "tool:write"),
    ("PATCH", "/tools/tools/{tool_id}", "tool:write"),
    ("PATCH", "/tools/tools/{tool_id}/status", "tool:write"),
    ("DELETE", "/tools/tools/{tool_id}", "tool:delete"),
    ("POST", "/tools/tools/test", "tool:execute"),
    ("POST", "/tools/tools/execute", "tool:execute"),
    ("GET", "/tools/agents/{agent_id}/tools", "tool:read"),
    ("GET", "/tools/secrets", "secret:read"),
    ("POST", "/tools/secrets", "secret:write"),
    ("GET", "/tools/tools/{tool_id}/usage-impact", "tool:read"),
    ("POST", "/tools/mcp/discover", "tool:write"),
    ("POST", "/tools/mcp/refresh", "tool:write"),
    ("PATCH", "/tools/mcp/permissions", "tool:write"),
    ("POST", "/tools/mcp/permissions/bulk", "tool:write"),
    ("POST", "/tools/mcp/oauth/start", "tool:write"),
    ("POST", "/tools/mcp/oauth/complete", "tool:write"),
    ("POST", "/tools/mcp/oauth/device/start", "tool:write"),
    ("POST", "/tools/mcp/oauth/device/poll", "tool:write"),
    ("POST", "/tools/mcp/oauth/status", "tool:write"),
    ("POST", "/tools/mcp/oauth/disconnect", "tool:write"),
    ("GET", "/ai/agents/{agent_id}/runtime-environments", "agent:read"),
    (
        "PATCH",
        "/ai/agents/{agent_id}/runtime-environments/{environment}",
        "agent:write",
    ),
    ("GET", "/network/{network_id}/runtime-environments", "network:read"),
    (
        "PATCH",
        "/network/{network_id}/runtime-environments/{environment}",
        "network:write",
    ),
    ("GET", "/metering/projects/{project_id}/usage", "usage:read"),
    ("GET", "/metering/projects/{project_id}/daily", "usage:read"),
    ("GET", "/metering/agents/{agent_id}/daily", "usage:read"),
    ("GET", "/observability/traces", "observability:read"),
    ("GET", "/observability/traces/{trace_id}", "observability:read"),
    ("GET", "/network/projects/{project_id}/networks", "network:read"),
    ("POST", "/network/projects/{project_id}/networks", "network:write"),
    (
        "DELETE",
        "/network/projects/{project_id}/networks/{network_id}",
        "network:delete",
    ),
    ("GET", "/network/projects/{project_id}/networks/{network_id}", "network:read"),
    ("PATCH", "/network/projects/{project_id}/networks/{network_id}", "network:write"),
    ("PUT", "/network/projects/{project_id}", "network:write"),
    ("GET", "/network/projects/{project_id}", "network:read"),
    ("PATCH", "/network/{network_id}/draft", "network:write"),
    ("POST", "/network/{network_id}/promotions/preview", "network:version"),
    ("POST", "/network/{network_id}/promotions", "network:version"),
    ("GET", "/network/{network_id}/versions", "network:read"),
    ("POST", "/network/{network_id}/rollback", "network:production"),
    ("GET", "/network/{network_id}/sessions", "run:read"),
    ("GET", "/network/{network_id}/sessions/{network_session_id}/messages", "run:read"),
    ("GET", "/network/executions/{execution_id}/events", "run:read"),
    ("GET", "/network/executions/active", "run:read"),
    ("GET", "/network/executions/{execution_id}/stream", "run:read"),
    ("GET", "/network/{network_id}/management/versions", "network:read"),
    (
        "GET",
        "/network/{network_id}/management/external-context-contract",
        "network:read",
    ),
    ("GET", "/network/{network_id}/management/activations", "network:read"),
    ("GET", "/network/executions/{execution_id}/snapshot", "run:read"),
    ("POST", "/network/{network_id}/production/activations", "network:production"),
    ("GET", "/network/executions/{execution_id}/diagnostics", "run:read"),
    ("GET", "/identity/permissions", "catalog:self"),
    ("GET", "/identity/access/me", "access:self"),
    ("POST", "/identity/access/check", "access:self"),
    (
        "PUT",
        "/identity/workspaces/{workspace_id}/authority-assignments/{subject_user_id}",
        "categories:assign",
    ),
    ("GET", "/identity/workspaces/{workspace_id}/authority-audit", "audit:read"),
]
_COMPILED = [
    (method, path, permission, compile_path(path)[0])
    for method, path, permission in _REVIEWED
]


def resolve_operation(
    method: str, path: str, body: Any = None
) -> tuple[str | None, dict[str, str]]:
    for allowed_method, template, permission, pattern in _COMPILED:
        match = pattern.fullmatch(path)
        if allowed_method != method.upper() or match is None:
            continue
        params = match.groupdict()
        data = body if isinstance(body, dict) else {}
        environment = params.get("environment") or data.get("environment")
        if template.endswith("/promotions"):
            permission = (
                "network:production"
                if environment == "production"
                else "network:version"
            )
        if (
            template.endswith("/runtime-environments/{environment}")
            and method.upper() == "PATCH"
            and environment == "production"
        ):
            permission = (
                "network:production"
                if template.startswith("/network/")
                else "agent:production"
            )
        if template.startswith("/runtime/runs/by-trace/"):
            params["run_trace_id"] = params.pop("trace_id")
        return permission, params
    return None, {}


def operation_catalog(routes) -> dict[str, Any]:
    from fastapi.routing import APIRoute

    reviewed = {(method, path): permission for method, path, permission in _REVIEWED}
    items = []
    for route in routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        for method in sorted(route.methods):
            permission = reviewed.get((method, route.path))
            items.append(
                {
                    "operation_id": route.unique_id,
                    "method": method,
                    "path": route.path,
                    "permission": permission,
                    "control_key_supported": permission is not None,
                    "principal_types": ["human", "control"]
                    if permission
                    else ["human"],
                    "effect": "read"
                    if method == "GET"
                    or permission in {"knowledge:read", "access:self"}
                    else "mutate",
                    "conditions": [
                        "environments",
                        "interfaces",
                        "target_types",
                        "target_ids",
                    ]
                    if permission
                    and permission.split(":")[0]
                    in {"agent", "network", "run", "api_key"}
                    else [],
                    "requires_if_match": permission
                    in {
                        "keys:update",
                        "keys:rotate",
                        "keys:revoke",
                        "categories:update",
                        "categories:archive",
                        "categories:delete",
                    },
                }
            )
    return {"revision": CATALOG_REVISION, "operations": items}
