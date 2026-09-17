from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from modules.agent.domain.external_context_contract import (
    ExternalContextContractError,
    classify_external_context_change,
    normalize_external_context_contract,
    resolve_external_context,
    validate_effective_external_context_values,
)
from modules.agent.domain.release_versioning import ReleaseChangeKind


@dataclass(frozen=True, slots=True)
class EffectiveExternalContextResolution:
    snapshot: dict[str, Any]
    session_values: dict[str, Any]


def _effective_fields(value: Any) -> dict[str, Any]:
    if value in (None, {}):
        return {}
    if not isinstance(value, dict) or not isinstance(value.get("fields"), dict):
        raise ExternalContextContractError("Effective External Context contract is invalid")
    fields = value["fields"]
    for name, field in fields.items():
        if not isinstance(name, str) or not name:
            raise ExternalContextContractError(
                "Effective External Context field names cannot be blank"
            )
        if not isinstance(field, dict):
            raise ExternalContextContractError(
                f"Effective External Context field '{name}' must be an object"
            )
        scope = field.get("scope", "run")
        if scope not in {"run", "session"}:
            raise ExternalContextContractError(
                f"Effective External Context field '{name}'.scope must be 'run' or 'session'"
            )
        consumers = field.get("consumers")
        if not isinstance(consumers, dict) or not consumers:
            raise ExternalContextContractError(
                f"Effective External Context field '{name}' must declare consumers"
            )
    return fields


def resolve_effective_external_context(
    effective_contract: Any,
    request_values: Any,
    *,
    session_values: Mapping[str, Any] | None = None,
) -> EffectiveExternalContextResolution:
    """Validate and freeze a Network External Context snapshot.

    Network acceptance validates only the effective request boundary. Per-Agent required/default
    semantics remain consumer-specific and are enforced when an Agent is invoked. Session-scoped
    values are reused across Runs in the same Network Session; run-scoped values are never reused.
    """

    fields = _effective_fields(effective_contract)
    raw_values = {} if request_values is None else request_values
    validated_request = validate_effective_external_context_values(
        {"fields": fields},
        raw_values,
    )
    persisted = dict(session_values or {})

    snapshot: dict[str, Any] = {}
    next_session_values: dict[str, Any] = {}
    for name, field in fields.items():
        scope = field.get("scope", "run")
        if name in validated_request:
            value = deepcopy(validated_request[name])
            snapshot[name] = value
            if scope == "session":
                next_session_values[name] = deepcopy(value)
            continue
        if scope == "session" and name in persisted:
            value = persisted[name]
            validate_effective_external_context_values(
                {"fields": {name: field}},
                {name: value},
            )
            snapshot[name] = deepcopy(value)
            next_session_values[name] = deepcopy(value)

    return EffectiveExternalContextResolution(
        snapshot=snapshot,
        session_values=next_session_values,
    )


def consumer_external_context_contract(
    effective_contract: Any,
    consumer: str,
) -> dict[str, Any]:
    """Reconstruct the Agent contract frozen inside one effective Network contract."""

    fields = _effective_fields(effective_contract)
    consumer_fields: dict[str, Any] = {}
    for name, field in fields.items():
        consumers = field.get("consumers") or {}
        consumer_spec = consumers.get(str(consumer))
        if not isinstance(consumer_spec, dict):
            continue
        model = consumer_spec.get("model")
        if not isinstance(model, dict):
            model = {"expose": False}
        reconstructed: dict[str, Any] = {
            "schema": deepcopy(field.get("schema") or {}),
            "required": bool(consumer_spec.get("required", False)),
            "scope": field.get("scope", "run"),
            "model": {"expose": bool(model.get("expose", False))},
        }
        if "default" in consumer_spec:
            reconstructed["default"] = deepcopy(consumer_spec["default"])
        consumer_fields[name] = reconstructed
    return normalize_external_context_contract({"fields": consumer_fields})


def project_effective_external_context(
    effective_contract: Any,
    consumer: str,
    snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project one immutable Network snapshot into the values accepted by one Agent.

    Required fields and Agent-specific defaults are enforced here, immediately before invoking the
    consumer. Values belonging only to other Agents never cross the Agent request boundary.
    """

    contract = consumer_external_context_contract(effective_contract, consumer)
    declared = contract["fields"]
    source = dict(snapshot or {})
    values = {
        name: deepcopy(source[name])
        for name in declared
        if name in source
    }
    return resolve_external_context(contract, values, enforce_required=True).snapshot


def _single_field_contract(
    name: str,
    field: Mapping[str, Any],
    consumer: Mapping[str, Any],
) -> dict[str, Any]:
    model = consumer.get("model")
    if not isinstance(model, dict):
        model = {"expose": False}
    value: dict[str, Any] = {
        "schema": deepcopy(field.get("schema") or {}),
        "required": bool(consumer.get("required", False)),
        "scope": field.get("scope", "run"),
        "model": {"expose": bool(model.get("expose", False))},
    }
    if "default" in consumer:
        value["default"] = deepcopy(consumer["default"])
    return {"fields": {name: value}}


def classify_effective_external_context_change(
    previous: Any,
    candidate: Any,
) -> ReleaseChangeKind:
    """Classify Network Release compatibility for the effective External Context boundary."""

    old_fields = _effective_fields(previous)
    new_fields = _effective_fields(candidate)
    if old_fields == new_fields:
        return ReleaseChangeKind.CHANGE

    if set(old_fields) - set(new_fields):
        # The Network boundary is strict; a formerly accepted field would become undeclared.
        return ReleaseChangeKind.COMPATIBILITY

    feature = False
    for name, new_field in new_fields.items():
        old_field = old_fields.get(name)
        new_consumers = new_field.get("consumers") or {}
        if old_field is None:
            if any(
                isinstance(spec, dict) and bool(spec.get("required", False))
                for spec in new_consumers.values()
            ):
                return ReleaseChangeKind.COMPATIBILITY
            feature = True
            continue

        old_consumers = old_field.get("consumers") or {}
        old_probe = {
            "fields": {
                name: {
                    "schema": deepcopy(old_field.get("schema") or {}),
                    "required": False,
                    "scope": old_field.get("scope", "run"),
                    "model": {"expose": False},
                }
            }
        }
        new_probe = {
            "fields": {
                name: {
                    "schema": deepcopy(new_field.get("schema") or {}),
                    "required": False,
                    "scope": new_field.get("scope", "run"),
                    "model": {"expose": False},
                }
            }
        }
        shape_kind = classify_external_context_change(old_probe, new_probe)
        if shape_kind is ReleaseChangeKind.COMPATIBILITY:
            return ReleaseChangeKind.COMPATIBILITY
        if shape_kind is ReleaseChangeKind.FEATURE:
            feature = True

        for consumer_name, new_consumer in new_consumers.items():
            if not isinstance(new_consumer, dict):
                raise ExternalContextContractError(
                    f"Effective External Context consumer '{consumer_name}' is invalid"
                )
            old_consumer = old_consumers.get(consumer_name)
            if old_consumer is None:
                if bool(new_consumer.get("required", False)):
                    return ReleaseChangeKind.COMPATIBILITY
                continue
            if not isinstance(old_consumer, dict):
                raise ExternalContextContractError(
                    f"Effective External Context consumer '{consumer_name}' is invalid"
                )
            consumer_kind = classify_external_context_change(
                _single_field_contract(name, old_field, old_consumer),
                _single_field_contract(name, new_field, new_consumer),
            )
            if consumer_kind is ReleaseChangeKind.COMPATIBILITY:
                return ReleaseChangeKind.COMPATIBILITY
            if consumer_kind is ReleaseChangeKind.FEATURE:
                feature = True

        removed_consumers = set(old_consumers) - set(new_consumers)
        if any(
            isinstance(old_consumers[name], dict)
            and bool(old_consumers[name].get("required", False))
            for name in removed_consumers
        ):
            feature = True

    return ReleaseChangeKind.FEATURE if feature else ReleaseChangeKind.CHANGE


def strongest_release_change(
    *kinds: ReleaseChangeKind,
) -> ReleaseChangeKind:
    if ReleaseChangeKind.COMPATIBILITY in kinds:
        return ReleaseChangeKind.COMPATIBILITY
    if ReleaseChangeKind.FEATURE in kinds:
        return ReleaseChangeKind.FEATURE
    return ReleaseChangeKind.CHANGE


__all__ = [
    "EffectiveExternalContextResolution",
    "classify_effective_external_context_change",
    "consumer_external_context_contract",
    "project_effective_external_context",
    "resolve_effective_external_context",
    "strongest_release_change",
]
