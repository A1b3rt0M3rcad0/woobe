from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any
from uuid import UUID

from modules.agent.application.mcp_permissions import normalize_permission
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import RiskLevel, ToolStatus, ToolType
from shared.infra.errors import ValidationError


def _value(value: object) -> object:
    return getattr(value, "value", value)


def _snapshot_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verify_snapshot_hash(snapshot: dict[str, Any]) -> None:
    expected = snapshot.get("snapshot_hash")
    if not isinstance(expected, str) or not expected:
        raise ValidationError("Release tool snapshot hash is missing")
    payload = {key: deepcopy(value) for key, value in snapshot.items() if key != "snapshot_hash"}
    if _snapshot_hash(payload) != expected:
        raise ValidationError("Release tool snapshot hash is invalid")


def tool_with_permission_overrides(tool: Tool, raw_permissions: Any) -> Tool:
    if not isinstance(raw_permissions, dict):
        return tool

    config = deepcopy(tool.config or {})
    discovered_tools = config.get("discovered_tools")
    if not isinstance(discovered_tools, list):
        return tool

    changed = False
    for item in discovered_tools:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        item["permission"] = normalize_permission(raw_permissions.get(name))
        changed = True

    if not changed:
        return tool

    cloned = deepcopy(tool)
    cloned.config = config
    return cloned


def tool_to_release_snapshot(tool: Tool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(tool.id),
        "project_id": str(tool.project_id) if tool.project_id else None,
        "name": tool.name,
        "description": tool.description,
        "type": str(_value(tool.type)),
        "config": deepcopy(tool.config or {}),
        "input_schema": deepcopy(tool.input_schema or {}),
        "output_schema": deepcopy(tool.output_schema) if tool.output_schema is not None else None,
        "risk_level": str(_value(tool.risk_level)),
        "timeout_ms": tool.timeout_ms,
        "status": str(_value(tool.status)),
    }
    payload["snapshot_hash"] = _snapshot_hash(payload)
    return payload


def tool_from_release_snapshot(snapshot: dict[str, Any]) -> Tool:
    _verify_snapshot_hash(snapshot)
    try:
        tool_id = UUID(str(snapshot["id"]))
        project_id_raw = snapshot.get("project_id")
        project_id = UUID(str(project_id_raw)) if project_id_raw else None
        tool_type = ToolType(str(snapshot.get("type") or ToolType.FUNCTION.value))
        risk_level = RiskLevel(str(snapshot.get("risk_level") or RiskLevel.LOW.value))
        status = ToolStatus(str(snapshot.get("status") or ToolStatus.ACTIVE.value))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Release contains an invalid tool snapshot") from exc

    return Tool(
        id=tool_id,
        project_id=project_id,
        name=str(snapshot.get("name") or ""),
        description=snapshot.get("description"),
        type=tool_type,
        config=deepcopy(snapshot.get("config") or {}),
        input_schema=deepcopy(snapshot.get("input_schema") or {}),
        output_schema=(
            deepcopy(snapshot.get("output_schema"))
            if snapshot.get("output_schema") is not None
            else None
        ),
        risk_level=risk_level,
        timeout_ms=snapshot.get("timeout_ms"),
        status=status,
    )


async def build_release_tool_runtime(
    tool_repo: Any,
    *,
    project_id: UUID,
    raw_tool_ids: list[object] | None,
    raw_permissions: Any = None,
) -> dict[str, Any]:
    ordered_ids: list[UUID] = []
    seen: set[UUID] = set()
    for raw_tool_id in raw_tool_ids or []:
        try:
            tool_id = raw_tool_id if isinstance(raw_tool_id, UUID) else UUID(str(raw_tool_id))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Draft contains an invalid tool id") from exc
        if tool_id not in seen:
            ordered_ids.append(tool_id)
            seen.add(tool_id)

    permission_map = raw_permissions if isinstance(raw_permissions, dict) else {}
    snapshots: list[dict[str, Any]] = []
    for tool_id in ordered_ids:
        tool = await tool_repo.get_by_id(tool_id)
        if tool is None:
            raise ValidationError(f"Selected tool was not found: {tool_id}")
        if tool.project_id != project_id:
            raise ValidationError("Selected tool does not belong to this Project")
        if _value(tool.status) != ToolStatus.ACTIVE.value:
            raise ValidationError(f"Selected tool is not active: {tool.name}")
        tool_permissions = permission_map.get(str(tool_id))
        snapshots.append(tool_to_release_snapshot(tool_with_permission_overrides(tool, tool_permissions)))

    return {
        "tool_ids": [str(tool_id) for tool_id in ordered_ids],
        "snapshots": snapshots,
    }
