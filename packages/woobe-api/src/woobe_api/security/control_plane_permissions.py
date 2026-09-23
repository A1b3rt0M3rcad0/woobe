from __future__ import annotations


def control_plane_permission(method: str, path: str) -> str | None:
    method = method.upper()

    if path.startswith("/core/workspaces/") and "/control-keys" in path:
        if method == "GET":
            return "keys:read"
        if path.endswith("/revoke") and method == "POST":
            return "keys:revoke"
        if path.endswith("/rotate") and method == "POST":
            return "keys:rotate"
        if method == "POST":
            return "keys:create"
        if method == "PATCH":
            return "keys:update"
        return None

    if path == "/core/projects" and method == "GET":
        return "workspace:read"

    if path.startswith("/core/projects/"):
        if "/environment-keys" in path:
            return (
                "project:environment:read"
                if method == "GET"
                else "project:environment:write"
                if method in {"PUT", "PATCH", "POST", "DELETE"}
                else None
            )
        if "/members" in path or "/access" in path:
            return (
                "project:access:read"
                if method == "GET"
                else "project:access:write"
                if method in {"POST", "PUT", "PATCH", "DELETE"}
                else None
            )
        if "/overview" in path or "/runs" in path:
            return "project:read" if method == "GET" else None
        if "/api-keys" in path or "/runtime-keys" in path:
            return (
                "api_key:read"
                if method == "GET"
                else "api_key:write"
                if method in {"POST", "PUT", "PATCH", "DELETE"}
                else None
            )
        if method == "GET":
            return "project:read"
        if method == "PATCH":
            return "project:update"
        return None

    if path.startswith("/ai/projects/") and "/skills" in path:
        if method == "GET":
            return "skill:read"
        if method == "POST" and "/versions" in path:
            return "skill:version"
        if method in {"POST", "PATCH"}:
            return "skill:write"
        if method == "DELETE":
            return "skill:delete"
        return None

    if path.startswith("/ai/credentials"):
        if path.endswith("/revoke") and method == "POST":
            return "provider:credential:revoke"
        if method == "GET":
            return "provider:read"
        if method in {"POST", "PATCH"}:
            return "provider:write"
        if method == "DELETE":
            return "provider:delete"
        return None

    if path.startswith("/ai/provider-models"):
        if method == "GET":
            return "model:read"
        if method in {"POST", "PATCH"}:
            return "model:write"
        if method == "DELETE":
            return "model:delete"
        return None

    if path.startswith("/ai/agents"):
        if "/releases" in path:
            if path.endswith("/promote") or path.endswith("/rollback"):
                return "agent:production" if method == "POST" else None
            if method == "POST":
                return "agent:version"
            if method == "DELETE":
                return "agent:version"
            return "agent:read" if method == "GET" else None
        if "/release-tests" in path:
            return "agent:version" if method == "POST" else "agent:read" if method == "GET" else None
        if "/prompts" in path or "/contracts" in path or "/model-configs" in path:
            return "agent:read" if method == "GET" else "agent:write" if method in {"POST", "PATCH"} else None
        if method == "GET":
            return "agent:read"
        if method in {"POST", "PATCH"}:
            return "agent:write"
        if method == "DELETE":
            return "agent:delete"
        return None

    if path.startswith("/knowledge") or path.startswith("/agent/knowledge"):
        if method == "GET":
            return "knowledge:read"
        if method == "DELETE":
            return "knowledge:delete"
        if method in {"POST", "PUT", "PATCH"}:
            return "knowledge:write"
        return None

    if path.startswith("/tools"):
        if path.endswith("/test") or path.endswith("/execute"):
            return "tool:execute" if method == "POST" else None
        if method == "GET":
            return "tool:read"
        if method == "DELETE":
            return "tool:delete"
        if method in {"POST", "PUT", "PATCH"}:
            return "tool:write"
        return None

    if path.startswith("/network/projects/"):
        if method == "GET":
            return "network:read"
        if method in {"POST", "PATCH"}:
            return "network:write"
        if method == "DELETE":
            return "network:delete"
        return None

    if path.startswith("/network/"):
        if path.endswith("/draft") and method == "PATCH":
            return "network:write"
        if path.endswith("/promotions/preview") and method == "POST":
            return "network:version"
        if path.endswith("/promotions") and method == "POST":
            return "network:production"
        if path.endswith("/rollback") and method == "POST":
            return "network:production"
        if path.endswith("/production/activations") and method == "POST":
            return "network:production"
        if "/management/versions" in path and method == "GET":
            return "network:read"
        if "/management/activations" in path and method == "GET":
            return "network:read"
        if "/management/external-context-contract" in path and method == "GET":
            return "network:read"
        if path.endswith("/versions") and method == "GET":
            return "network:read"
        return None

    if path.startswith("/observability/") and method == "GET":
        return "observability:read"

    if path.startswith("/metering/") and method == "GET":
        return "usage:read"

    return None
