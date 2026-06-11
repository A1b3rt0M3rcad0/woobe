from __future__ import annotations

import json
from uuid import UUID

from modules.tools.domain.entities import Tool
from modules.tools.domain.enums import ToolType


def tool_to_openai_definition(tool: Tool) -> dict:
    """
    Converts a Tool entity into an OpenAI-compatible tool definition dict.
    """
    config = tool.config or {}
    input_schema = tool.input_schema or _build_input_schema(config)

    return {
        "type": "function",
        "function": {
            "name": safe_tool_name(tool),
            "description": tool.description or f"HTTP {config.get('method', 'GET')} {config.get('url', '')}",
            "parameters": input_schema,
        },
    }


def tools_to_openai_definitions(tools: list[Tool]) -> list[dict]:
    return [tool_to_openai_definition(t) for t in tools]


def safe_tool_name(tool: Tool) -> str:
    name = tool.name.lower().strip().replace(" ", "_").replace("-", "_")
    name = "".join(c for c in name if c.isalnum() or c == "_")
    if not name or name[0].isdigit():
        name = f"tool_{name}"
    return name


def _build_input_schema(config: dict) -> dict:
    """
    Build a JSON Schema for input parameters from the config.
    Extracts variables from URL and body template, creating flat individual properties.
    """
    url = config.get("url", "")
    body_template = config.get("body", "")

    variables = _extract_url_variables(url)
    if body_template:
        for v in _extract_url_variables(body_template):
            if v not in variables:
                variables.append(v)

    properties = {}
    required = []

    for var_name in variables:
        properties[var_name] = {
            "type": "string",
            "description": f"Parameter {var_name}",
        }
        required.append(var_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _extract_url_variables(url: str) -> list[str]:
    import re
    matches = re.findall(r'\{\{(\w+)\}\}', url)
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result
