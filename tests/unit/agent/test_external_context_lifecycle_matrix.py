from __future__ import annotations

from copy import deepcopy

from modules.agent.domain.external_context_contract import (
    model_external_context,
    resolve_external_context,
)


def _field(
    field_type: str | list[str],
    *,
    scope: str = "run",
    required: bool = False,
    expose: bool = False,
    default=None,
) -> dict:
    field = {
        "schema": {"type": field_type},
        "required": required,
        "scope": scope,
        "model": {"expose": expose},
    }
    if default is not None:
        field["default"] = deepcopy(default)
    return field


def test_request_value_overrides_persisted_session_value_and_becomes_next_session_value() -> None:
    contract = {
        "name": _field(
            "string",
            scope="session",
            required=True,
            expose=True,
            default="Anonymous",
        )
    }

    resolved = resolve_external_context(
        contract,
        {"name": "Joao"},
        session_values={"name": "Alberto"},
    )

    assert resolved.snapshot == {"name": "Joao"}
    assert resolved.session_values == {"name": "Joao"}
    assert model_external_context(contract, resolved.snapshot) == {"name": "Joao"}


def test_session_value_wins_over_default_when_request_omits_field() -> None:
    contract = {
        "name": _field(
            "string",
            scope="session",
            required=True,
            expose=True,
            default="Anonymous",
        )
    }

    resolved = resolve_external_context(
        contract,
        {},
        session_values={"name": "Alberto"},
    )

    assert resolved.snapshot == {"name": "Alberto"}
    assert resolved.session_values == {"name": "Alberto"}


def test_default_is_used_when_request_and_session_do_not_supply_field() -> None:
    contract = {
        "locale": _field(
            "string",
            scope="session",
            required=True,
            expose=True,
            default="pt-BR",
        )
    }

    resolved = resolve_external_context(contract, {}, session_values={})

    assert resolved.snapshot == {"locale": "pt-BR"}
    assert resolved.session_values == {"locale": "pt-BR"}


def test_explicit_null_is_a_real_session_value_when_schema_allows_null() -> None:
    contract = {
        "nickname": _field(
            ["string", "null"],
            scope="session",
            required=False,
            expose=True,
        )
    }

    resolved = resolve_external_context(
        contract,
        {"nickname": None},
        session_values={"nickname": "Alberto"},
    )

    assert resolved.snapshot == {"nickname": None}
    assert resolved.session_values == {"nickname": None}
    assert model_external_context(contract, resolved.snapshot) == {"nickname": None}


def test_omitted_run_field_never_reuses_stale_session_storage() -> None:
    contract = {
        "current_page": _field(
            "string",
            scope="run",
            required=False,
            expose=True,
        )
    }

    resolved = resolve_external_context(
        contract,
        {},
        session_values={"current_page": "/stale-page"},
    )

    assert resolved.snapshot == {}
    assert resolved.session_values == {}


def test_removed_contract_field_is_dropped_from_next_session_values() -> None:
    contract = {
        "name": _field("string", scope="session", expose=True),
    }

    resolved = resolve_external_context(
        contract,
        {},
        session_values={
            "name": "Alberto",
            "removed_field": "must-not-survive",
        },
    )

    assert resolved.snapshot == {"name": "Alberto"}
    assert resolved.session_values == {"name": "Alberto"}


def test_execution_snapshot_is_deeply_immutable_from_request_and_session_inputs() -> None:
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
            "scope": "session",
            "model": {"expose": True},
        }
    }
    request = {"profile": {"roles": ["admin"]}}
    persisted = {"profile": {"roles": ["viewer"]}}

    resolved = resolve_external_context(
        contract,
        request,
        session_values=persisted,
    )
    request["profile"]["roles"].append("mutated-after-resolution")
    persisted["profile"]["roles"].append("mutated-after-resolution")

    assert resolved.snapshot == {"profile": {"roles": ["admin"]}}
    assert resolved.session_values == {"profile": {"roles": ["admin"]}}
