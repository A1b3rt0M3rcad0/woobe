"""Advertise existing DTO contracts without moving parsing before authorization."""
from __future__ import annotations

from typing import Any
import re

from pydantic import BaseModel


def request_body_contract(model: type[BaseModel], path: str, method: str, *, required: bool = True) -> dict[str, Any]:
    schema = model.model_json_schema(mode="validation")
    # Inline DTO definitions live under the request schema, not OpenAPI's root.
    # Root-relative pointers must address that location, including escaped paths.
    pointer = "#/paths/" + path.replace("~", "~0").replace("/", "~1")
    pointer += "/" + method.lower() + "/requestBody/content/application~1json/schema"

    def relocate(value: Any) -> None:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                value["$ref"] = pointer + ref[1:]
            for key, child in value.items():
                if key not in {"default", "const", "enum", "examples", "example"}:
                    relocate(child)
        elif isinstance(value, list):
            for child in value:
                relocate(child)

    relocate(schema)
    return {
        "requestBody": {"required": required, "content": {"application/json": {"schema": schema}}},
        "parameters": [
            {"name": name, "in": "path", "required": True,
             "schema": {"type": "string", **({"format": "uuid"} if name.endswith("_id") else {})}}
            for name in re.findall(r"\{([^}]+)\}", path)
        ],
    }
