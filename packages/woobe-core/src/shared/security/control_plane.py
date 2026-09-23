from __future__ import annotations

WORKSPACE_CONTROL_PERMISSIONS = frozenset(
    {
        "workspace:read",
        "keys:read",
        "keys:create",
        "keys:update",
        "keys:revoke",
        "keys:rotate",
    }
)

PROJECT_CONTROL_PERMISSIONS = frozenset(
    {
        "project:read",
        "project:update",
        "project:environment:read",
        "project:environment:write",
        "project:access:read",
        "project:access:write",
        "agent:read",
        "agent:write",
        "agent:delete",
        "agent:version",
        "agent:production",
        "network:read",
        "network:write",
        "network:delete",
        "network:version",
        "network:production",
        "tool:read",
        "tool:write",
        "tool:delete",
        "tool:execute",
        "knowledge:read",
        "knowledge:write",
        "knowledge:delete",
        "provider:read",
        "provider:write",
        "provider:delete",
        "provider:credential:revoke",
        "model:read",
        "model:write",
        "model:delete",
        "skill:read",
        "skill:write",
        "skill:delete",
        "skill:version",
        "observability:read",
        "usage:read",
    }
)

ALL_CONTROL_PERMISSIONS = WORKSPACE_CONTROL_PERMISSIONS | PROJECT_CONTROL_PERMISSIONS


def normalize_permissions(
    permissions: list[str],
    *,
    allowed: frozenset[str],
) -> list[str]:
    normalized = list(dict.fromkeys(str(item).strip() for item in permissions))
    if any(not item for item in normalized):
        raise ValueError("Permission cannot be blank")
    unknown = set(normalized) - allowed
    if unknown:
        raise ValueError(
            "Unsupported control-plane permissions: " + ", ".join(sorted(unknown))
        )
    return normalized


def is_permission_subset(
    requested: set[str] | frozenset[str],
    available: set[str] | frozenset[str],
) -> bool:
    return requested.issubset(available)
