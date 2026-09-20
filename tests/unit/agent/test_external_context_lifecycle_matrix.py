from __future__ import annotations

from copy import deepcopy

from modules.agent.domain.external_context_contract import (
    model_external_context,
    resolve_external_context,
)


def _field(
    field_type: str | list[str],
    *,
    required: bool = False,
    expose: bool = False,
    default=None,
) -> dict:
    field = {
        "schema": {"type": field_type},
        "required": required,
        "model": {"expose": expose},
    }
    if default is not None:
        field["default"] = deepcopy(default)
    return field


def test_request_value_wins_over_default_for_current_run() -> None:
    contract = {
        "name": _field(
            "string",
            required=True,
            expose=True,
            default="Anonymous",
        )
    }

    resolved = resolve_external_context(contract, {"name": "Joao"})

    assert resolved.snapshot == {"name": "Joao"}
    assert model_external_context(contract, resolved.snapshot) == {"name": "Joao"}


def test_default_is_used_when_request_omits_field() -> None:
    contract = {
        "locale": _field(
            "string",
            required=True,
            expose=True,
            default="pt-BR",
        )
    }

    resolved = resolve_external_context(contract, {})

    assert resolved.snapshot == {"locale": "pt-BR"}


def test_explicit_null_is_a_real_run_value_when_schema_allows_null() -> None:
    contract = {
        "nickname": _field(
            ["string", "null"],
            required=False,
            expose=True,
        )
    }

    resolved = resolve_external_context(contract, {"nickname": None})

    assert resolved.snapshot == {"nickname": None}
    assert model_external_context(contract, resolved.snapshot) == {"nickname": None}


def test_omitted_optional_field_is_not_recovered_from_previous_runs() -> None:
    contract = {
        "current_page": _field(
            "string",
            required=False,
            expose=True,
        )
    }

    first = resolve_external_context(contract, {"current_page": "/checkout"})
    second = resolve_external_context(contract, {})

    assert first.snapshot == {"current_page": "/checkout"}
    assert second.snapshot == {}


def test_execution_snapshot_is_deeply_immutable_from_request_input() -> None:
    contract = {
        "profile": {
            "schema": {
                "type": "object",
                "properties": {
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
                "required": ["roles"],
                "additionalProperties": False,
            },
            "required": True,
            "model": {"expose": True},
        }
    }
    request = {"profile": {"roles": ["admin"]}}

    resolved = resolve_external_context(contract, request)
    request["profile"]["roles"].append("mutated-after-resolution")

    assert resolved.snapshot == {"profile": {"roles": ["admin"]}}
