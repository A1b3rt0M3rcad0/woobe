from __future__ import annotations

import json
from copy import deepcopy
from typing import Any
from urllib.parse import quote

from modules.agent.application.interfaces.http_tool_contract import (
    CompiledHttpToolContract,
    HttpToolContractError,
    TEMPLATE_PATTERN,
)


def _resolve_inputs(
    contract: CompiledHttpToolContract,
    input_data: dict[str, Any] | None,
) -> dict[str, Any]:
    provided = input_data or {}
    properties = contract.input_schema.get("properties")
    if contract.input_schema.get("additionalProperties") is False:
        allowed = set(properties) if isinstance(properties, dict) else set()
        unexpected = sorted(str(name) for name in provided if name not in allowed)
        if unexpected:
            raise HttpToolContractError(
                "HTTP_TOOL_PARAMETER_UNEXPECTED",
                "Unexpected HTTP Tool parameters: " + ", ".join(unexpected),
            )

    defaults = contract.config.get("variables")
    inputs = {
        **(defaults if isinstance(defaults, dict) else {}),
        **provided,
    }
    required = contract.input_schema.get("required")
    missing = [
        str(name)
        for name in (required if isinstance(required, list) else [])
        if name not in inputs or inputs[name] in (None, "")
    ]
    if missing:
        raise HttpToolContractError(
            "HTTP_TOOL_PARAMETER_MISSING",
            "Missing required HTTP Tool parameters: " + ", ".join(missing),
            missing=missing,
        )
    return inputs


def _replace(value: str, inputs: dict[str, Any], *, encode: bool = False) -> str:
    def render(match) -> str:
        name = match.group(1)
        if name not in inputs or inputs[name] is None:
            raise HttpToolContractError(
                "HTTP_TOOL_PARAMETER_MISSING",
                f"Missing required HTTP Tool parameter: {name}",
                missing=[name],
            )
        text = str(inputs[name])
        return quote(text, safe="") if encode else text

    rendered = TEMPLATE_PATTERN.sub(render, value)
    unresolved = TEMPLATE_PATTERN.findall(rendered)
    if unresolved:
        raise HttpToolContractError(
            "HTTP_TOOL_RENDER_FAILED",
            "Unresolved HTTP Tool parameters: " + ", ".join(unresolved),
            missing=unresolved,
        )
    return rendered


def _render_json(value: Any, inputs: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _render_json(item, inputs) for key, item in value.items()}
    if isinstance(value, list):
        return [_render_json(item, inputs) for item in value]
    if not isinstance(value, str):
        return value
    match = TEMPLATE_PATTERN.fullmatch(value)
    if match:
        name = match.group(1)
        if name not in inputs or inputs[name] is None:
            raise HttpToolContractError(
                "HTTP_TOOL_PARAMETER_MISSING",
                f"Missing required HTTP Tool parameter: {name}",
                missing=[name],
            )
        return inputs[name]
    return _replace(value, inputs)


def _is_json(headers: dict[str, str]) -> bool:
    return any(
        key.lower() == "content-type"
        and ("application/json" in value.lower() or "+json" in value.lower())
        for key, value in headers.items()
    )


def render_http_tool_request(
    contract: CompiledHttpToolContract,
    input_data: dict[str, Any] | None,
    headers: dict[str, str] | None,
) -> tuple[str, dict[str, str], str | None]:
    inputs = _resolve_inputs(contract, input_data)
    url = _replace(str(contract.config.get("url") or ""), inputs, encode=True)
    rendered_headers: dict[str, str] = {}
    for key, value in (headers or {}).items():
        rendered = _replace(str(value), inputs)
        if "\r" in rendered or "\n" in rendered:
            raise HttpToolContractError(
                "HTTP_TOOL_RENDER_FAILED",
                f"HTTP Tool header '{key}' contains an invalid line break.",
            )
        rendered_headers[str(key)] = rendered

    body = contract.config.get("body")
    if body is None:
        return url, rendered_headers, None
    if _is_json(rendered_headers):
        if isinstance(body, str):
            try:
                parsed = json.loads(body)
            except (TypeError, ValueError) as exc:
                raise HttpToolContractError(
                    "HTTP_TOOL_BODY_JSON_INVALID",
                    "HTTP Tool Body must be valid JSON for application/json.",
                ) from exc
        else:
            parsed = deepcopy(body)
        return url, rendered_headers, json.dumps(
            _render_json(parsed, inputs),
            separators=(",", ":"),
            ensure_ascii=False,
        )
    if isinstance(body, str):
        return url, rendered_headers, _replace(body, inputs)
    return url, rendered_headers, json.dumps(
        _render_json(body, inputs),
        ensure_ascii=False,
    )
