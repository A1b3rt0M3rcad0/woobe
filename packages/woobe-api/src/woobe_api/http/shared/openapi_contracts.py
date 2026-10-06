"""Advertise existing DTO contracts without moving parsing before authorization."""
from __future__ import annotations

from typing import Any
import re

from pydantic import BaseModel


def request_body_contract(model: type[BaseModel], path: str, method: str, *, required: bool = True, path_fields: tuple[str, ...] = (), advertise_path: bool = True) -> dict[str, Any]:
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

    _relocate(schema, pointer)
    contract: dict[str, Any] = {"requestBody": {"required": required, "content": {"application/json": {"schema": schema}}}}
    # FastAPI already generates parameters for typed handler arguments.
    # Its openapi_extra merge concatenates lists, so adding them again is invalid.
    if advertise_path:
        contract["parameters"] = [
            {"name": name, "in": "path", "required": True,
             "schema": path_schemas.get(name, {"type": "string", **({"format": "uuid"} if name.endswith("_id") else {})})}
            for name in names
        ]
    return contract


def _relocate(value: Any, pointer: str) -> None:
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
                    _relocate(child, pointer)
        for keyword in ("additionalProperties", "unevaluatedProperties", "propertyNames", "items", "contains", "not", "if", "then", "else", "unevaluatedItems"):
            child = value.get(keyword)
            if isinstance(child, dict):
                _relocate(child, pointer)
        for keyword in ("allOf", "anyOf", "oneOf", "prefixItems"):
            children = value.get(keyword)
            if isinstance(children, list):
                for child in children:
                    _relocate(child, pointer)


def query_parameter_contract(model: type[BaseModel], path: str, *, query_fields: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Advertise only parameters actually consumed by a reviewed controller."""
    from copy import deepcopy

    root = model.model_json_schema(mode="validation")
    properties = root.get("properties", {})
    path_names = re.findall(r"\{([^}]+)\}", path)
    query_names = list(query_fields) if query_fields is not None else [name for name in properties if name not in path_names]
    if len(query_names) != len(set(query_names)) or any(name not in properties or name in path_names for name in query_names):
        raise ValueError("Query fields must be unique consumed DTO properties outside the path")
    parameters = []
    for name in path_names + query_names:
        location = "path" if name in path_names else "query"
        schema = deepcopy(properties.get(name, {"type": "string", **({"format": "uuid"} if name.endswith("_id") else {})}))
        if "$defs" in root:
            schema["$defs"] = deepcopy(root["$defs"])
        pointer = "#/paths/" + path.replace("~", "~0").replace("/", "~1") + "/get/parameters/" + str(len(parameters)) + "/schema"
        _relocate(schema, pointer)
        parameters.append({"name": name, "in": location, "required": location == "path" or name in root.get("required", []), "schema": schema})
    return {"parameters": parameters}
