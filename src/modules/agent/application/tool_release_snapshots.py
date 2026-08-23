from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any
from uuid import UUID

from modules.agent.application.http_tool_contract import (
    compile_http_tool_group_contract,
    compile_http_tool_contract,
    is_http_tool_group,
)
from modules.agent.application.mcp_permissions import normalize_permission
from modules.agent.application.tool_types import is_http_tool_type
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import RiskLevel, ToolStatus, ToolType
from modules.agent.domain.errors import ToolNotFoundError
from shared.contracts.errors import ValidationError


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


def _snapshot_index(raw_snapshots: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_snapshots, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for snapshot in raw_snapshots:
        if isinstance(snapshot, dict) and snapshot.get("id") is not None:
            result[str(snapshot["id"])] = snapshot
    return result


def _apply_child_permissions(items: Any, raw_permissions: dict[str, Any], *, keys: tuple[str, ...]) -> bool:
    if not isinstance(items, list):
        return False
    changed = False
    for item in items:
        if not isinstance(item, dict):
            continue
        identifiers = [str(item.get(key) or "") for key in keys]
        identifier = next((value for value in identifiers if value), None)
        if identifier is None:
            continue
        item["permission"] = normalize_permission(raw_permissions.get(identifier))
        changed = True
    return changed


def _collect_child_permissions(items: Any, *, keys: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    permissions: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        identifier = next(
            (
                str(item.get(key) or "").strip()
                for key in keys
                if str(item.get(key) or "").strip()
            ),
            None,
        )
        if not identifier:
            continue
        raw_permission = item.get("permission")
        if raw_permission is None:
            raw_permission = {
                "mode": item.get("default_permission") or "review",
                "risk_level": item.get("risk_level"),
            }
        permissions[identifier] = normalize_permission(raw_permission)
    return permissions


def _tool_child_permissions(tool: Tool) -> dict[str, dict[str, Any]]:
    config = tool.config or {}
    permissions = _collect_child_permissions(
        config.get("discovered_tools"),
        keys=("name",),
    )
    permissions.update(
        _collect_child_permissions(
            config.get("routes"),
            keys=("id", "operation_id"),
        )
    )
    return permissions


def tool_with_permission_overrides(tool: Tool, raw_permissions: Any) -> Tool:
    if not isinstance(raw_permissions, dict):
        return tool
    config = deepcopy(tool.config or {})
    changed = _apply_child_permissions(
        config.get("discovered_tools"),
        raw_permissions,
        keys=("name",),
    )
    changed = _apply_child_permissions(
        config.get("routes"),
        raw_permissions,
        keys=("id", "operation_id"),
    ) or changed
    if not changed:
        return tool
    cloned = deepcopy(tool)
    cloned.config = config
    return cloned


def tool_to_release_snapshot(tool: Tool) -> dict[str, Any]:
    config = deepcopy(tool.config or {})
    input_schema = deepcopy(tool.input_schema or {})
    contract = None
    group_contract = None
    if is_http_tool_type(tool.type):
        if is_http_tool_group(config):
            group_contract = compile_http_tool_group_contract(config)
            config = group_contract.config
            input_schema = {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            }
        else:
            contract = compile_http_tool_contract(config, input_schema)
            config = contract.config
            input_schema = contract.input_schema
    payload: dict[str, Any] = {
        "id": str(tool.id),
        "project_id": str(tool.project_id) if tool.project_id else None,
        "name": tool.name,
        "description": tool.description,
        "type": str(_value(tool.type)),
        "config": config,
        "input_schema": input_schema,
        "output_schema": deepcopy(tool.output_schema) if tool.output_schema is not None else None,
        "risk_level": str(_value(tool.risk_level)),
        "timeout_ms": tool.timeout_ms,
        "status": str(_value(tool.status)),
    }
    if contract:
        payload["http_contract_version"] = contract.version
        payload["http_contract_hash"] = contract.contract_hash
    if group_contract:
        payload["http_group_contract_version"] = group_contract.version
        payload["http_group_contract_hash"] = group_contract.contract_hash
        payload["http_route_contract_hashes"] = {
            route_id: compiled.contract_hash
            for route_id, compiled in group_contract.route_contracts.items()
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
        output_schema=deepcopy(snapshot.get("output_schema")) if snapshot.get("output_schema") is not None else None,
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
    previous_snapshots: Any = None,
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
    previous_snapshot_map = _snapshot_index(previous_snapshots)
    snapshots: list[dict[str, Any]] = []
    effective_permissions: dict[str, dict[str, dict[str, Any]]] = {}
    for tool_id in ordered_ids:
        try:
            live_tool = await tool_repo.get_by_id(tool_id)
        except ToolNotFoundError:
            live_tool = None
        if live_tool is not None and live_tool.project_id != project_id:
            raise ValidationError("Selected tool does not belong to this Project")
        if live_tool is not None and _value(live_tool.status) == ToolStatus.ACTIVE.value:
            source_tool = live_tool
        else:
            previous_snapshot = previous_snapshot_map.get(str(tool_id))
            if previous_snapshot is None:
                if live_tool is None:
                    raise ValidationError(f"Selected tool was not found: {tool_id}")
                raise ValidationError(f"Selected tool is not active: {live_tool.name}")
            source_tool = tool_from_release_snapshot(previous_snapshot)
            if source_tool.id != tool_id:
                raise ValidationError("Draft contains a mismatched tool snapshot")
            if source_tool.project_id != project_id:
                raise ValidationError("Draft tool snapshot does not belong to this Project")
        effective_tool = tool_with_permission_overrides(source_tool, permission_map.get(str(tool_id)))
        snapshots.append(tool_to_release_snapshot(effective_tool))
        effective_permissions[str(tool_id)] = _tool_child_permissions(effective_tool)

    return {
        "tool_ids": [str(tool_id) for tool_id in ordered_ids],
        "permissions": effective_permissions,
        "snapshots": snapshots,
    }
