"""Advertise existing DTO contracts without moving parsing before authorization."""
from __future__ import annotations

from typing import Any
import re

from pydantic import BaseModel


def request_body_contract(model: type[BaseModel], path: str, method: str, *, required: bool = True, path_fields: tuple[str, ...] = ()) -> dict[str, Any]:
    schema = model.model_json_schema(mode="validation")
    names = re.findall(r"\{([^}]+)\}", path)
    properties = schema.get("properties", {})
    path_schemas = {}
    for name in path_fields:
        if name not in names or name not in properties:
            raise ValueError("Injected path fields must belong to both route and DTO")
        path_schemas[name] = properties.pop(name)
    if path_fields:
        required_fields = [name for name in schema.get("required", []) if name not in path_fields]
        if required_fields:
            schema["required"] = required_fields
        else:
            schema.pop("required", None)
    # Inline DTO definitions live under the request schema, not OpenAPI's root.
    # Root-relative pointers must address that location, including escaped paths.
    pointer = "#/paths/" + path.replace("~", "~0").replace("/", "~1")
    pointer += "/" + method.lower() + "/requestBody/content/application~1json/schema"

    def relocate(value: Any) -> None:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                value["$ref"] = pointer + ref[1:]
            # Property/definition names can themselves be "default", "enum"
            # or "$ref". Interpret keywords only at schema nodes.
            for keyword in ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas"):
                children = value.get(keyword)
                if isinstance(children, dict):
                    for child in children.values():
                        relocate(child)
            for keyword in ("additionalProperties", "unevaluatedProperties", "propertyNames", "items", "contains", "not", "if", "then", "else", "unevaluatedItems"):
                child = value.get(keyword)
                if isinstance(child, dict):
                    relocate(child)
            for keyword in ("allOf", "anyOf", "oneOf", "prefixItems"):
                children = value.get(keyword)
                if isinstance(children, list):
                    for child in children:
                        relocate(child)

    relocate(schema)
    return {
        "requestBody": {"required": required, "content": {"application/json": {"schema": schema}}},
        "parameters": [
            {"name": name, "in": "path", "required": True,
             "schema": path_schemas.get(name, {"type": "string", **({"format": "uuid"} if name.endswith("_id") else {})})}
            for name in names
        ],
    }
