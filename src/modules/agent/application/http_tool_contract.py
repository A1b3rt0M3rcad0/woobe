from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

HTTP_TOOL_CONTRACT_VERSION = 1
TEMPLATE_PATTERN = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")
_SINGLE_BRACE_PATTERN = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")


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
