from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

CATALOG_REVISION = "2026-10-05.1"
SELF_CONTROL_PERMISSIONS = frozenset({"access:self", "catalog:self"})

WORKSPACE_CONTROL_PERMISSIONS = frozenset(
    {
        "workspace:read",
        "projects:create",
        "keys:read",
        "keys:create",
        "keys:update",
        "keys:revoke",
        "keys:rotate",
        "categories:read",
        "categories:create",
        "categories:update",
        "categories:archive",
        "categories:delete",
        "categories:assign",
        "audit:read",
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
        "api_key:read",
        "api_key:write",
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
        "provider:credential:rotate",
        "provider:credential:revoke",
        "model:read",
        "model:write",
        "model:delete",
        "skill:read",
        "skill:write",
        "skill:version",
        "chat_surface:read",
        "chat_surface:write",
        "chat_surface:release",
        "chat_surface:keys",
        "run:read",
        "observability:read",
        "usage:read",
        "catalog:read",
        "run:execute",
        "run:cancel",
        "run:stream",
        "secret:read",
        "secret:write",
        "secret:delete",
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


def is_read_permission(permission: str) -> bool:
    return (
        permission.endswith(":read")
        or permission in SELF_CONTROL_PERMISSIONS
        or permission == "run:stream"
    )


def system_profiles() -> dict[str, tuple[str, list[str]]]:
    return {
        "project-reader": (
            "project",
            sorted(
                p
                for p in PROJECT_CONTROL_PERMISSIONS
                if is_read_permission(p) and not p.startswith("secret:")
            ),
        ),
        "agent-editor": ("project", ["agent:read", "agent:write"]),
        "network-editor": ("project", ["network:read", "network:write"]),
        "knowledge-editor": ("project", ["knowledge:read", "knowledge:write"]),
        "version-builder": (
            "project",
            ["agent:read", "agent:version", "network:read", "network:version"],
        ),
        "production-publisher": (
            "project",
            ["agent:read", "agent:production", "network:read", "network:production"],
        ),
        "runtime-observer": (
            "project",
            ["run:read", "run:stream", "observability:read", "usage:read"],
        ),
        "project-administrator": ("project", sorted(PROJECT_CONTROL_PERMISSIONS)),
        "workspace-key-manager": (
            "workspace",
            sorted(
                p
                for p in WORKSPACE_CONTROL_PERMISSIONS
                if p.startswith("keys:") or p in {"categories:read", "workspace:read"}
            ),
        ),
    }


def expand_permissions(
    permissions: list[str], *, scope: str, catalog_revision: str | None = None
) -> list[str]:
    if scope not in {"workspace", "project"}:
        raise ValueError("Category scope must be workspace or project")
    allowed = (
        WORKSPACE_CONTROL_PERMISSIONS
        if scope == "workspace"
        else PROJECT_CONTROL_PERMISSIONS
    )
    result: set[str] = set()
    for permission in permissions:
        if not isinstance(permission, str):
            raise ValueError("Permissions must be strings")
        if "*" in permission:
            if catalog_revision != CATALOG_REVISION:
                raise ValueError(
                    "Wildcard expansion requires the current catalog revision"
                )
            if permission != "*" and not permission.endswith(":*"):
                raise ValueError("Only complete namespace wildcards are supported")
            prefix = permission[:-1]
            matched = {p for p in allowed if permission == "*" or p.startswith(prefix)}
            if not matched:
                raise ValueError("Wildcard does not match a known permission namespace")
            result.update(matched)
        else:
            result.update(normalize_permissions([permission], allowed=allowed))
    return sorted(result)


def require_expiration_ceiling(
    expires_at: datetime | None, ceiling: datetime | None
) -> None:
    for value in (expires_at, ceiling):
        if value is not None and value.tzinfo is None:
            raise ValueError("Expiration must include a timezone")
    if expires_at is not None and expires_at <= datetime.now(UTC):
        raise ValueError("Expiration must be in the future")
    if ceiling is not None and (expires_at is None or expires_at > ceiling):
        raise ValueError("Expiration cannot exceed the delegation ceiling")


def normalize_conditions(value: dict[str, Any] | None) -> dict[str, list[str]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Grant conditions must be an object")
    allowed = {
        "environments": {"staging", "production"},
        "interfaces": {"http", "stream", "jobs"},
        "target_types": {"agent", "network"},
        "target_ids": None,
    }
    if set(value) - set(allowed):
        raise ValueError("Unknown grant condition")
    result = {}
    for name, values in value.items():
        if (
            not isinstance(values, list)
            or len(values) > 128
            or any(not isinstance(v, str) for v in values)
        ):
            raise ValueError("Grant conditions must contain bounded lists of strings")
        if name == "target_ids":
            try:
                result[name] = sorted({str(UUID(v)) for v in values})
            except ValueError as exc:
                raise ValueError("Invalid target identifier") from exc
        else:
            if set(values) - allowed[name]:
                raise ValueError("Unsupported grant condition value")
            result[name] = sorted(set(values))
    return result


def conditions_are_subset(requested: dict[str, Any], available: dict[str, Any]) -> bool:
    requested = normalize_conditions(requested)
    available = normalize_conditions(available)
    return all(
        name in requested and set(requested[name]) <= set(values)
        for name, values in available.items()
    )


def conditions_allow(
    conditions: dict[str, Any],
    *,
    environment: str | None = None,
    target_type: str | None = None,
    target_id: UUID | str | None = None,
    interfaces: list[str] | None = None,
) -> bool:
    checks = {
        "environments": environment,
        "target_types": target_type,
        "target_ids": str(target_id) if target_id is not None else None,
    }
    for name, item in checks.items():
        if item is not None and name in conditions and item not in conditions[name]:
            return False
    return (
        interfaces is None
        or "interfaces" not in conditions
        or set(interfaces) <= set(conditions["interfaces"])
    )
