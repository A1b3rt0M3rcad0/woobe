from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from modules.agent.domain.release_versioning import ReleaseChangeKind


_MISSING = object()


class ExternalContextContractError(ValueError):
    """Raised when an External Context contract or payload is invalid."""


@dataclass(frozen=True, slots=True)
class ExternalContextResolution:
    snapshot: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ScopedExternalContextResolution:
    session_snapshot: dict[str, Any]
    run_snapshot: dict[str, Any]
    snapshot: dict[str, Any]
    session_changed: bool


def _raw_contract_fields(value: Any) -> dict[str, Any]:
    """Return the field map while accepting the pre-builder PR shape for transition reads."""

    if value in (None, {}):
        return {}
    if not isinstance(value, dict):
        raise ExternalContextContractError("External Context contract must be an object")

    if set(value).issubset({"fields", "additionalProperties"}) and isinstance(
        value.get("fields"), dict
    ):
        return value["fields"]

    return value


def normalize_external_context_contract(value: Any) -> dict[str, Any]:
    """Return the canonical top-level External Context field map."""

    raw_fields = _raw_contract_fields(value)
    fields: dict[str, Any] = {}

    for raw_name, raw_field in raw_fields.items():
        name = str(raw_name).strip()
        if not name:
            raise ExternalContextContractError("External Context field names cannot be blank")
        if name in fields:
            raise ExternalContextContractError(f"Duplicate External Context field: {name}")
        if not isinstance(raw_field, dict):
            raise ExternalContextContractError(
                f"External Context field '{name}' must be an object"
            )

        unknown_field_keys = set(raw_field) - {
            "schema",
            "required",
            "default",
            "model",
            "description",
            "scope",
        }
        if unknown_field_keys:
            names = ", ".join(sorted(str(key) for key in unknown_field_keys))
            raise ExternalContextContractError(
                f"External Context field '{name}' contains unknown properties: {names}"
            )

        scope = raw_field.get("scope", "run")
        if scope not in {"run", "session"}:
            raise ExternalContextContractError(
                f"External Context field '{name}'.scope must be 'run' or 'session'"
            )

        schema = _normalize_schema(raw_field.get("schema", {}), field_name=name)
        required = raw_field.get("required", False)
        if not isinstance(required, bool):
            raise ExternalContextContractError(
                f"External Context field '{name}'.required must be boolean"
            )

        model = raw_field.get("model", {})
        if model is None:
            model = {}
        if not isinstance(model, dict) or set(model) - {"expose"}:
            raise ExternalContextContractError(
                f"External Context field '{name}'.model only supports the 'expose' property"
            )
        expose = model.get("expose", False)
        if not isinstance(expose, bool):
            raise ExternalContextContractError(
                f"External Context field '{name}'.model.expose must be boolean"
            )

        field: dict[str, Any] = {
            "schema": schema,
            "required": required,
            "model": {"expose": expose},
        }
        if "scope" in raw_field:
            field["scope"] = scope
        if "default" in raw_field:
            _validate_schema_value(raw_field["default"], schema, f"{name}.default")
            field["default"] = deepcopy(raw_field["default"])
        if raw_field.get("description") is not None:
            if not isinstance(raw_field["description"], str):
                raise ExternalContextContractError(
                    f"External Context field '{name}'.description must be a string"
                )
            field["description"] = raw_field["description"]
        fields[name] = field

    return fields


def resolve_external_context(
    contract: Any,
    request_values: Any,
    *,
    enforce_required: bool = True,
) -> ExternalContextResolution:
    """Validate request values and freeze one immutable execution snapshot."""

    fields = normalize_external_context_contract(contract)
    raw_values = {} if request_values is None else request_values
    if not isinstance(raw_values, dict):
        raise ExternalContextContractError("External Context values must be an object")

    unknown = set(raw_values) - set(fields)
    if unknown:
        names = ", ".join(sorted(str(key) for key in unknown))
        raise ExternalContextContractError(
            f"External Context contains undeclared fields: {names}"
        )

    snapshot: dict[str, Any] = {}

    for name, field in fields.items():
        value: Any = _MISSING
        if name in raw_values:
            value = raw_values[name]
        elif "default" in field:
            value = deepcopy(field["default"])

        if value is _MISSING:
            if enforce_required and field["required"]:
                raise ExternalContextContractError(
                    f"Required External Context field is missing: {name}"
                )
            continue

        _validate_schema_value(value, field["schema"], name)
        snapshot[name] = deepcopy(value)
    return ExternalContextResolution(snapshot=snapshot)


def split_external_context_contract(
    contract: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split one canonical contract by lifecycle scope."""

    fields = normalize_external_context_contract(contract)
    session_fields = {
        name: deepcopy(field)
        for name, field in fields.items()
        if field.get("scope", "run") == "session"
    }
    run_fields = {
        name: deepcopy(field)
        for name, field in fields.items()
        if field.get("scope", "run") == "run"
    }
    return session_fields, run_fields


def resolve_scoped_external_context(
    contract: Any,
    request_values: Any,
    *,
    session_snapshot: Mapping[str, Any] | None,
    allow_session_replay: bool = False,
) -> ScopedExternalContextResolution:
    """Resolve immutable Session values plus ephemeral Run values."""

    fields = normalize_external_context_contract(contract)
    values = {} if request_values is None else request_values
    if not isinstance(values, dict):
        raise ExternalContextContractError("External Context values must be an object")

    unknown = set(values) - set(fields)
    if unknown:
        names = ", ".join(sorted(str(key) for key in unknown))
        raise ExternalContextContractError(
            f"External Context contains undeclared fields: {names}"
        )

    session_fields, run_fields = split_external_context_contract(fields)
    session_values = {
        name: deepcopy(values[name])
        for name in session_fields
        if name in values
    }
    run_values = {
        name: deepcopy(values[name])
        for name in run_fields
        if name in values
    }

    session_changed = False
    if session_fields:
        if session_snapshot is None:
            resolved_session = resolve_external_context(
                session_fields,
                session_values,
                enforce_required=True,
            ).snapshot
            session_changed = True
        else:
            persisted = deepcopy(dict(session_snapshot))
            checked = resolve_external_context(
                session_fields,
                persisted,
                enforce_required=True,
            ).snapshot
            if checked != persisted:
                raise ExternalContextContractError(
                    "Session External Context no longer satisfies the active contract; "
                    "open a new Session"
                )

            if session_values:
                if not allow_session_replay:
                    names = ", ".join(sorted(session_values))
                    raise ExternalContextContractError(
                        "Session-scoped External Context is immutable and cannot be "
                        f"supplied again: {names}"
                    )
                mismatched = [
                    name
                    for name, value in session_values.items()
                    if name not in persisted or persisted[name] != value
                ]
                if mismatched:
                    names = ", ".join(sorted(mismatched))
                    raise ExternalContextContractError(
                        "Session-scoped External Context is immutable and cannot be "
                        f"overwritten: {names}"
                    )
            resolved_session = persisted
    else:
        resolved_session = {}

    resolved_run = resolve_external_context(
        run_fields,
        run_values,
        enforce_required=True,
    ).snapshot
    effective = deepcopy(resolved_session)
    effective.update(deepcopy(resolved_run))
    return ScopedExternalContextResolution(
        session_snapshot=deepcopy(resolved_session),
        run_snapshot=deepcopy(resolved_run),
        snapshot=effective,
        session_changed=session_changed,
    )


def project_external_context(contract: Any, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Project a shared snapshot to the fields declared by one Agent."""

    fields = normalize_external_context_contract(contract)
    projected = {name: deepcopy(snapshot[name]) for name in fields if name in snapshot}
    resolve_external_context(fields, projected, enforce_required=True)
    return projected


def model_external_context(contract: Any, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Return only External Context values explicitly exposed to the model."""

    fields = normalize_external_context_contract(contract)
    return {
        name: deepcopy(snapshot[name])
        for name, field in fields.items()
        if field["model"]["expose"] and name in snapshot
    }


def classify_external_context_change(previous: Any, candidate: Any) -> ReleaseChangeKind:
    """Classify Release compatibility caused by External Context changes."""

    old_fields = normalize_external_context_contract(previous)
    new_fields = normalize_external_context_contract(candidate)
    if old_fields == new_fields:
        return ReleaseChangeKind.CHANGE
    if set(old_fields) - set(new_fields):
        return ReleaseChangeKind.COMPATIBILITY

    feature = False
    for name, new_field in new_fields.items():
        old_field = old_fields.get(name)
        if old_field is None:
            if new_field["required"]:
                return ReleaseChangeKind.COMPATIBILITY
            feature = True
            continue

        if old_field.get("scope", "run") != new_field.get("scope", "run"):
            return ReleaseChangeKind.COMPATIBILITY
        if not old_field["required"] and new_field["required"]:
            return ReleaseChangeKind.COMPATIBILITY
        if _schema_breaks_input_compatibility(old_field["schema"], new_field["schema"]):
            return ReleaseChangeKind.COMPATIBILITY

        if old_field["required"] and not new_field["required"]:
            feature = True
        if _schema_expands_input(old_field["schema"], new_field["schema"]):
            feature = True

    return ReleaseChangeKind.FEATURE if feature else ReleaseChangeKind.CHANGE


def compose_external_context_contracts(
    contracts: Mapping[str, Any],
) -> dict[str, Any]:
    """Compose Agent contracts into the Network top-level effective field map."""

    effective_fields: dict[str, Any] = {}
    for consumer, raw_contract in contracts.items():
        contract = normalize_external_context_contract(raw_contract)
        for name, field in contract.items():
            existing = effective_fields.get(name)
            if existing is None:
                existing = {
                    "schema": deepcopy(field["schema"]),
                    "consumers": {},
                }
                if "scope" in field:
                    existing["scope"] = field["scope"]
                effective_fields[name] = existing
            elif (
                existing["schema"] != field["schema"]
                or existing.get("scope", "run") != field.get("scope", "run")
            ):
                raise ExternalContextContractError(
                    f"External Context field '{name}' conflicts between Network Agents"
                )
            elif "scope" in field and "scope" not in existing:
                # Preserve an explicitly declared lifecycle when it is semantically
                # equivalent to the legacy implicit run scope.
                existing["scope"] = field["scope"]

            consumer_contract: dict[str, Any] = {
                "required": field["required"],
                "model": deepcopy(field["model"]),
            }
            if "default" in field:
                consumer_contract["default"] = deepcopy(field["default"])
            if "description" in field:
                consumer_contract["description"] = field["description"]
            existing["consumers"][str(consumer)] = consumer_contract

    return effective_fields


def _effective_fields(effective_contract: Any) -> dict[str, Any]:
    if effective_contract in (None, {}):
        return {}
    if not isinstance(effective_contract, dict):
        raise ExternalContextContractError("Effective External Context contract is invalid")
    if set(effective_contract).issubset({"fields", "additionalProperties"}) and isinstance(
        effective_contract.get("fields"), dict
    ):
        return effective_contract["fields"]
    return effective_contract


def validate_effective_external_context_values(
    effective_contract: Any,
    request_values: Any,
) -> dict[str, Any]:
    """Validate the Network request boundary without imposing per-Agent required fields."""

    fields = _effective_fields(effective_contract)
    values = {} if request_values is None else request_values
    if not isinstance(values, dict):
        raise ExternalContextContractError("External Context values must be an object")
    unknown = set(values) - set(fields)
    if unknown:
        names = ", ".join(sorted(str(key) for key in unknown))
        raise ExternalContextContractError(
            f"External Context contains undeclared fields: {names}"
        )

    snapshot: dict[str, Any] = {}
    for name, value in values.items():
        schema = fields[name].get("schema", {}) if isinstance(fields[name], dict) else {}
        _validate_schema_value(value, schema, name)
        snapshot[name] = deepcopy(value)
    return snapshot


def _normalize_schema(value: Any, *, field_name: str) -> dict[str, Any]:
    if isinstance(value, str):
        value = {"type": value}
    if not isinstance(value, dict):
        raise ExternalContextContractError(
            f"External Context field '{field_name}'.schema must be an object"
        )
    schema = deepcopy(value)
    raw_type = schema.get("type")
    if raw_type is not None and not (
        isinstance(raw_type, str)
        or (isinstance(raw_type, list) and all(isinstance(item, str) for item in raw_type))
    ):
        raise ExternalContextContractError(
            f"External Context field '{field_name}'.schema.type is invalid"
        )
    if "enum" in schema and not isinstance(schema["enum"], list):
        raise ExternalContextContractError(
            f"External Context field '{field_name}'.schema.enum must be an array"
        )
    if "properties" in schema and not isinstance(schema["properties"], dict):
        raise ExternalContextContractError(
            f"External Context field '{field_name}'.schema.properties must be an object"
        )
    return schema


def _validate_schema_value(value: Any, schema: Mapping[str, Any], path: str) -> None:
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        raise ExternalContextContractError(
            f"External Context field '{path}' must be one of the declared enum values"
        )

    raw_type = schema.get("type")
    allowed_types = raw_type if isinstance(raw_type, list) else [raw_type] if raw_type else []
    if allowed_types and not any(_matches_type(value, item) for item in allowed_types):
        expected = " | ".join(str(item) for item in allowed_types)
        raise ExternalContextContractError(
            f"External Context field '{path}' must match type {expected}"
        )

    if isinstance(value, dict):
        properties = schema.get("properties")
        required = schema.get("required", [])
        if isinstance(required, list):
            missing = [name for name in required if name not in value]
            if missing:
                raise ExternalContextContractError(
                    f"External Context field '{path}' is missing required properties: "
                    + ", ".join(str(name) for name in missing)
                )
        if isinstance(properties, dict):
            if schema.get("additionalProperties") is False:
                unknown = set(value) - set(properties)
                if unknown:
                    raise ExternalContextContractError(
                        f"External Context field '{path}' contains undeclared properties: "
                        + ", ".join(sorted(str(name) for name in unknown))
                    )
            for name, child_schema in properties.items():
                if name in value and isinstance(child_schema, dict):
                    _validate_schema_value(value[name], child_schema, f"{path}.{name}")

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            _validate_schema_value(item, schema["items"], f"{path}[{index}]")


def _matches_type(value: Any, expected: Any) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return True


def _schema_breaks_input_compatibility(
    previous: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> bool:
    if previous == candidate:
        return False
    if previous.get("type") != candidate.get("type"):
        return True

    old_enum = previous.get("enum")
    new_enum = candidate.get("enum")
    if isinstance(old_enum, list):
        if not isinstance(new_enum, list):
            return False
        if not set(old_enum).issubset(set(new_enum)):
            return True
    elif isinstance(new_enum, list):
        return True

    ignored = {"description", "title", "default", "enum"}
    old_structural = {key: value for key, value in previous.items() if key not in ignored}
    new_structural = {key: value for key, value in candidate.items() if key not in ignored}
    return old_structural != new_structural


def _schema_expands_input(
    previous: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> bool:
    old_enum = previous.get("enum")
    new_enum = candidate.get("enum")
    if isinstance(old_enum, list) and isinstance(new_enum, list):
        return bool(set(new_enum) - set(old_enum)) and set(old_enum).issubset(set(new_enum))
    if isinstance(old_enum, list) and new_enum is None:
        return True
    return False
