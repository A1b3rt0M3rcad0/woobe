from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

HTTP_TOOL_CONTRACT_VERSION = 1
HTTP_TOOL_GROUP_CONTRACT_VERSION = 2
HTTP_TOOL_GROUP_MODE = "group"
TEMPLATE_PATTERN = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")
_SINGLE_BRACE_PATTERN = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")
_OPERATION_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PERMISSION_MODES = {"allow", "deny", "review"}
_ROUTE_STATUSES = {"active", "inactive"}
_ROUTE_RISKS = {"low", "medium", "high", "critical"}


class HttpToolContractError(ValueError):
    def __init__(self, code: str, message: str, *, missing: list[str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.missing = missing or []


@dataclass(frozen=True)
class CompiledHttpToolContract:
    config: dict[str, Any]
    input_schema: dict[str, Any]
    parameter_names: tuple[str, ...]
    contract_hash: str
    version: int = HTTP_TOOL_CONTRACT_VERSION


@dataclass(frozen=True)
class CompiledHttpToolGroupContract:
    config: dict[str, Any]
    route_contracts: dict[str, CompiledHttpToolContract]
    contract_hash: str
    version: int = HTTP_TOOL_GROUP_CONTRACT_VERSION


def is_http_tool_group(config: dict[str, Any] | None) -> bool:
    raw = config or {}
    return raw.get("mode") == HTTP_TOOL_GROUP_MODE or (
        isinstance(raw.get("routes"), list) and bool(raw.get("base_url"))
    )


def _template_sources(config: dict[str, Any]) -> list[str]:
    body = config.get("body")
    body_text = body if isinstance(body, str) else json.dumps(body, default=str) if body is not None else ""
    sources = [str(config.get("url") or ""), body_text]
    for header in config.get("headers") or []:
        if isinstance(header, dict):
            sources.append(str(header.get("value") or ""))
    return sources


def _parameter_names(config: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for source in _template_sources(config):
        malformed = _SINGLE_BRACE_PATTERN.search(source)
        if malformed:
            name = malformed.group(1)
            raise HttpToolContractError(
                "HTTP_TOOL_TEMPLATE_INVALID",
                f"Invalid placeholder '{{{name}}}'. Use '{{{{{name}}}}}'.",
            )
        for name in TEMPLATE_PATTERN.findall(source):
            if name not in names:
                names.append(name)
    return names


def _has_default(config: dict[str, Any], name: str) -> bool:
    defaults = config.get("variables")
    return isinstance(defaults, dict) and name in defaults and defaults[name] not in (None, "")


def compile_http_tool_contract(
    config: dict[str, Any] | None,
    declared_schema: dict[str, Any] | None = None,
) -> CompiledHttpToolContract:
    normalized = deepcopy(config or {})
    names = _parameter_names(normalized)
    schema = deepcopy(declared_schema or {})
    if not isinstance(schema, dict) or schema.get("type") not in (None, "object"):
        raise HttpToolContractError(
            "HTTP_TOOL_INPUT_INVALID",
            "HTTP Tool input_schema must be an object schema.",
        )
    schema["type"] = "object"
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    properties = deepcopy(properties)
    for name in names:
        properties.setdefault(name, {"type": "string", "description": f"Parameter {name}"})
    schema["properties"] = properties
    raw_required = schema.get("required")
    required = [name for name in raw_required if isinstance(name, str) and name in properties] if isinstance(raw_required, list) else []
    for name in names:
        if not _has_default(normalized, name) and name not in required:
            required.append(name)
    schema["required"] = required
    schema.setdefault("additionalProperties", False)
    payload = {"version": HTTP_TOOL_CONTRACT_VERSION, "config": normalized, "input_schema": schema}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return CompiledHttpToolContract(
        config=normalized,
        input_schema=schema,
        parameter_names=tuple(names),
        contract_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


def _normalize_base_url(value: Any) -> str:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HttpToolContractError(
            "HTTP_TOOL_GROUP_BASE_URL_INVALID",
            "HTTP API base_url must be an absolute HTTP or HTTPS URL.",
        )
    if parsed.query or parsed.fragment:
        raise HttpToolContractError(
            "HTTP_TOOL_GROUP_BASE_URL_INVALID",
            "HTTP API base_url cannot contain query parameters or fragments.",
        )
    return raw.rstrip("/")


def _normalize_headers(raw_headers: Any, *, field_name: str) -> list[dict[str, Any]]:
    if raw_headers is None:
        return []
    if not isinstance(raw_headers, list):
        raise HttpToolContractError("HTTP_TOOL_HEADERS_INVALID", f"{field_name} must be a list.")
    headers: list[dict[str, Any]] = []
    for raw in raw_headers:
        if not isinstance(raw, dict):
            raise HttpToolContractError("HTTP_TOOL_HEADERS_INVALID", f"{field_name} contains an invalid header.")
        key = str(raw.get("key") or "").strip()
        if not key:
            continue
        headers.append(
            {
                "key": key,
                "value": str(raw.get("value") or ""),
                **({"sensitive": bool(raw.get("sensitive"))} if raw.get("sensitive") is not None else {}),
            }
        )
    return headers


def _merge_headers(shared: list[dict[str, Any]], route: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    indexes: dict[str, int] = {}
    for header in [*shared, *route]:
        key = str(header.get("key") or "").strip()
        if not key:
            continue
        normalized_key = key.lower()
        if normalized_key in indexes:
            ordered[indexes[normalized_key]] = deepcopy(header)
        else:
            indexes[normalized_key] = len(ordered)
            ordered.append(deepcopy(header))
    return ordered


def http_route_permission_mode(route: dict[str, Any]) -> str:
    permission = route.get("permission")
    if isinstance(permission, dict):
        mode = str(permission.get("mode") or "").lower()
        if mode in _PERMISSION_MODES:
            return mode
    elif isinstance(permission, str) and permission.lower() in _PERMISSION_MODES:
        return permission.lower()
    default_permission = str(route.get("default_permission") or "review").lower()
    return default_permission if default_permission in _PERMISSION_MODES else "review"


def http_group_route(config: dict[str, Any], route_identifier: str) -> dict[str, Any] | None:
    wanted = str(route_identifier or "").strip()
    for raw in config.get("routes") or []:
        if not isinstance(raw, dict):
            continue
        if wanted in {str(raw.get("id") or ""), str(raw.get("operation_id") or "")}:
            return raw
    return None


def flatten_http_group_route(
    config: dict[str, Any],
    route: dict[str, Any],
) -> dict[str, Any]:
    base_url = _normalize_base_url(config.get("base_url"))
    path = str(route.get("path") or "").strip()
    parsed_path = urlparse(path)
    if parsed_path.scheme or parsed_path.netloc:
        raise HttpToolContractError(
            "HTTP_TOOL_ROUTE_PATH_INVALID",
            "HTTP route path must be relative to the group base_url.",
        )
    if not path:
        raise HttpToolContractError("HTTP_TOOL_ROUTE_PATH_INVALID", "HTTP route path is required.")
    url = f"{base_url}/{path.lstrip('/')}"
    shared_headers = _normalize_headers(config.get("headers"), field_name="HTTP API headers")
    route_headers = _normalize_headers(route.get("headers"), field_name="HTTP route headers")
    normalized: dict[str, Any] = {
        "protocol": "http",
        "method": str(route.get("method") or "GET").upper(),
        "url": url,
        "headers": _merge_headers(shared_headers, route_headers),
        "variables": deepcopy(route.get("variables") or {}),
        "timeout_ms": route.get("timeout_ms") or config.get("timeout_ms"),
    }
    if route.get("body") is not None:
        normalized["body"] = deepcopy(route.get("body"))
    if config.get("auth") is not None:
        normalized["auth"] = deepcopy(config.get("auth"))
    return {key: value for key, value in normalized.items() if value is not None}


def compile_http_group_route_contract(
    config: dict[str, Any],
    route_identifier: str,
) -> CompiledHttpToolContract:
    route = http_group_route(config, route_identifier)
    if route is None:
        raise HttpToolContractError(
            "HTTP_TOOL_ROUTE_NOT_FOUND",
            f"HTTP route '{route_identifier}' was not found in this Tool.",
        )
    return compile_http_tool_contract(
        flatten_http_group_route(config, route),
        route.get("input_schema") if isinstance(route.get("input_schema"), dict) else None,
    )


def allowed_http_group_routes(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        route
        for route in config.get("routes") or []
        if isinstance(route, dict)
        and str(route.get("status") or "active").lower() == "active"
        and http_route_permission_mode(route) == "allow"
    ]


def compile_http_tool_group_contract(
    config: dict[str, Any] | None,
) -> CompiledHttpToolGroupContract:
    normalized = deepcopy(config or {})
    normalized["protocol"] = "http"
    normalized["mode"] = HTTP_TOOL_GROUP_MODE
    normalized["schema_version"] = HTTP_TOOL_GROUP_CONTRACT_VERSION
    normalized["base_url"] = _normalize_base_url(normalized.get("base_url"))
    normalized["headers"] = _normalize_headers(normalized.get("headers"), field_name="HTTP API headers")
    raw_routes = normalized.get("routes")
    if not isinstance(raw_routes, list) or not raw_routes:
        raise HttpToolContractError(
            "HTTP_TOOL_GROUP_ROUTES_REQUIRED",
            "HTTP API group requires at least one route.",
        )

    route_ids: set[str] = set()
    operation_ids: set[str] = set()
    compiled_routes: list[dict[str, Any]] = []
    route_contracts: dict[str, CompiledHttpToolContract] = {}

    for index, raw_route in enumerate(raw_routes, start=1):
        if not isinstance(raw_route, dict):
            raise HttpToolContractError(
                "HTTP_TOOL_ROUTE_INVALID",
                f"HTTP route {index} is invalid.",
            )
        route = deepcopy(raw_route)
        route_id = str(route.get("id") or "").strip()
        operation_id = str(route.get("operation_id") or "").strip()
        name = str(route.get("name") or "").strip()
        description = str(route.get("description") or "").strip()
        method = str(route.get("method") or "GET").upper()
        status = str(route.get("status") or "active").lower()
        risk_level = str(route.get("risk_level") or "low").lower()
        default_permission = str(route.get("default_permission") or "review").lower()

        if not route_id:
            raise HttpToolContractError("HTTP_TOOL_ROUTE_ID_REQUIRED", f"HTTP route {index} requires id.")
        if route_id in route_ids:
            raise HttpToolContractError("HTTP_TOOL_ROUTE_ID_DUPLICATE", f"Duplicate HTTP route id '{route_id}'.")
        if not operation_id or not _OPERATION_ID_PATTERN.fullmatch(operation_id):
            raise HttpToolContractError(
                "HTTP_TOOL_OPERATION_ID_INVALID",
                f"HTTP route '{name or index}' requires a valid operation_id using letters, numbers and underscores.",
            )
        if operation_id in operation_ids:
            raise HttpToolContractError(
                "HTTP_TOOL_OPERATION_ID_DUPLICATE",
                f"Duplicate HTTP route operation_id '{operation_id}'.",
            )
        if not name:
            raise HttpToolContractError("HTTP_TOOL_ROUTE_NAME_REQUIRED", f"HTTP route {index} requires a name.")
        if not description:
            raise HttpToolContractError(
                "HTTP_TOOL_ROUTE_DESCRIPTION_REQUIRED",
                f"HTTP route '{name}' requires a description for the Agent.",
            )
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
            raise HttpToolContractError("HTTP_TOOL_METHOD_INVALID", f"Unsupported HTTP method '{method}'.")
        if status not in _ROUTE_STATUSES:
            raise HttpToolContractError("HTTP_TOOL_ROUTE_STATUS_INVALID", f"Invalid route status '{status}'.")
        if risk_level not in _ROUTE_RISKS:
            raise HttpToolContractError("HTTP_TOOL_ROUTE_RISK_INVALID", f"Invalid route risk '{risk_level}'.")
        if default_permission not in _PERMISSION_MODES:
            raise HttpToolContractError(
                "HTTP_TOOL_ROUTE_PERMISSION_INVALID",
                f"Invalid default permission '{default_permission}'.",
            )

        route_ids.add(route_id)
        operation_ids.add(operation_id)
        route.update(
            {
                "id": route_id,
                "operation_id": operation_id,
                "name": name,
                "description": description,
                "method": method,
                "status": status,
                "risk_level": risk_level,
                "default_permission": default_permission,
                "headers": _normalize_headers(route.get("headers"), field_name=f"Headers for route '{name}'"),
            }
        )
        contract = compile_http_tool_contract(
            flatten_http_group_route(normalized, route),
            route.get("input_schema") if isinstance(route.get("input_schema"), dict) else None,
        )
        route["input_schema"] = contract.input_schema
        route["contract_version"] = contract.version
        route["contract_hash"] = contract.contract_hash
        compiled_routes.append(route)
        route_contracts[route_id] = contract

    normalized["routes"] = compiled_routes
    payload = {"version": HTTP_TOOL_GROUP_CONTRACT_VERSION, "config": normalized}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return CompiledHttpToolGroupContract(
        config=normalized,
        route_contracts=route_contracts,
        contract_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )
