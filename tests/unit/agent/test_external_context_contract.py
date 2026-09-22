from __future__ import annotations

import pytest

from modules.agent.domain.external_context_contract import (
    ExternalContextContractError,
    classify_external_context_change,
    compose_external_context_contracts,
    normalize_external_context_contract,
    project_external_context,
    resolve_external_context,
    resolve_scoped_external_context,
    validate_effective_external_context_values,
)
from modules.agent.domain.release_versioning import ReleaseChangeKind


def contract(
    *,
    required: bool = False,
    expose: bool = False,
    field_type: str = "string",
    scope: str = "run",
):
    return {
        "customer_id": {
            "schema": {"type": field_type},
            "required": required,
            "scope": scope,
            "model": {"expose": expose},
        }
    }


def test_contract_is_a_top_level_field_map() -> None:
    normalized = normalize_external_context_contract(contract())
    assert set(normalized) == {"customer_id"}
    assert "fields" not in normalized


def test_legacy_fields_wrapper_is_read_compatible_but_normalizes_flat() -> None:
    normalized = normalize_external_context_contract({"fields": contract()})
    assert normalized == contract()


@pytest.mark.parametrize("scope", ["run", "session"])
def test_scope_is_preserved_in_canonical_contract(scope: str) -> None:
    normalized = normalize_external_context_contract(contract(scope=scope))
    assert normalized["customer_id"]["scope"] == scope


def test_missing_scope_defaults_to_run_without_rewriting_legacy_snapshot() -> None:
    raw = contract()
    raw["customer_id"].pop("scope")

    normalized = normalize_external_context_contract(raw)
    resolved = resolve_scoped_external_context(
        normalized,
        {"customer_id": "cus-1"},
        session_snapshot=None,
    )

    assert "scope" not in normalized["customer_id"]
    assert resolved.session_snapshot == {}
    assert resolved.run_snapshot == {"customer_id": "cus-1"}


def test_invalid_scope_is_rejected() -> None:
    raw = contract()
    raw["customer_id"]["scope"] = "project"
    with pytest.raises(ExternalContextContractError, match="scope must be 'run' or 'session'"):
        normalize_external_context_contract(raw)


def test_scope_change_breaks_release_compatibility() -> None:
    assert (
        classify_external_context_change(
            contract(scope="run"),
            contract(scope="session"),
        )
        == ReleaseChangeKind.COMPATIBILITY
    )


def test_unknown_request_fields_are_rejected() -> None:
    with pytest.raises(ExternalContextContractError, match="undeclared fields"):
        resolve_external_context(contract(), {"unknown": "value"})


def test_required_field_is_enforced_on_every_resolution() -> None:
    with pytest.raises(ExternalContextContractError, match="customer_id"):
        resolve_external_context(contract(required=True), {})


def test_type_validation_happens_before_execution() -> None:
    with pytest.raises(ExternalContextContractError, match="type string"):
        resolve_external_context(contract(required=True), {"customer_id": 42})


def test_model_exposure_does_not_change_agent_projection() -> None:
    projected = project_external_context(
        contract(required=True, expose=False),
        {"customer_id": "cus-1", "network_only": "hidden"},
    )
    assert projected == {"customer_id": "cus-1"}


def test_add_optional_field_is_feature() -> None:
    previous = {}
    candidate = contract(required=False)
    assert classify_external_context_change(previous, candidate) == ReleaseChangeKind.FEATURE


def test_add_required_field_breaks_compatibility() -> None:
    previous = {"fields": {}}
    candidate = contract(required=True)
    assert (
        classify_external_context_change(previous, candidate)
        == ReleaseChangeKind.COMPATIBILITY
    )


def test_removing_optional_field_breaks_because_contract_is_strict() -> None:
    assert (
        classify_external_context_change(contract(required=False), {})
        == ReleaseChangeKind.COMPATIBILITY
    )


def test_optional_to_required_breaks_compatibility() -> None:
    assert (
        classify_external_context_change(
            contract(required=False),
            contract(required=True),
        )
        == ReleaseChangeKind.COMPATIBILITY
    )


def test_required_to_optional_is_non_breaking_feature() -> None:
    assert (
        classify_external_context_change(
            contract(required=True),
            contract(required=False),
        )
        == ReleaseChangeKind.FEATURE
    )


def test_enum_widening_is_feature_and_narrowing_breaks() -> None:
    previous = {
        "locale": {
            "schema": {"type": "string", "enum": ["pt-BR"]},
            "required": False,
        }
    }
    widened = {
        "locale": {
            "schema": {"type": "string", "enum": ["pt-BR", "en-US"]},
            "required": False,
        }
    }
    assert classify_external_context_change(previous, widened) == ReleaseChangeKind.FEATURE
    assert (
        classify_external_context_change(widened, previous)
        == ReleaseChangeKind.COMPATIBILITY
    )


def test_network_contract_composes_consumers_without_global_required() -> None:
    effective = compose_external_context_contracts(
        {
            "support": contract(required=True, expose=True),
            "orders": contract(required=False, expose=False),
        }
    )
    field = effective["customer_id"]
    assert field["schema"] == {"type": "string"}
    assert field["consumers"]["support"]["required"] is True
    assert field["consumers"]["orders"]["required"] is False
    assert "required" not in field
    assert field["scope"] == "run"


def test_network_contract_rejects_schema_conflicts() -> None:
    with pytest.raises(ExternalContextContractError, match="conflicts"):
        compose_external_context_contracts(
            {
                "support": contract(field_type="string"),
                "orders": contract(field_type="integer"),
            }
        )


def test_effective_network_boundary_is_strict_but_defers_required_to_consumer() -> None:
    effective = compose_external_context_contracts(
        {"orders": contract(required=True)}
    )
    assert validate_effective_external_context_values(effective, {}) == {}
    with pytest.raises(ExternalContextContractError, match="undeclared"):
        validate_effective_external_context_values(effective, {"unknown": 1})


def test_network_contract_rejects_scope_conflicts() -> None:
    with pytest.raises(ExternalContextContractError, match="conflicts"):
        compose_external_context_contracts(
            {
                "support": contract(scope="session"),
                "orders": contract(scope="run"),
            }
        )


def test_scoped_resolution_freezes_session_and_replaces_run_values() -> None:
    scoped_contract = {
        "customer_id": {
            "schema": {"type": "string"},
            "required": True,
            "scope": "session",
            "model": {"expose": False},
        },
        "current_page": {
            "schema": {"type": "string"},
            "required": False,
            "scope": "run",
            "model": {"expose": True},
        },
    }

    first = resolve_scoped_external_context(
        scoped_contract,
        {"customer_id": "cus-1", "current_page": "/checkout"},
        session_snapshot=None,
    )
    second = resolve_scoped_external_context(
        scoped_contract,
        {"current_page": "/orders"},
        session_snapshot=first.session_snapshot,
    )

    assert first.session_changed is True
    assert first.session_snapshot == {"customer_id": "cus-1"}
    assert first.run_snapshot == {"current_page": "/checkout"}
    assert second.session_changed is False
    assert second.snapshot == {
        "customer_id": "cus-1",
        "current_page": "/orders",
    }


def test_scoped_resolution_rejects_repeated_session_values() -> None:
    scoped_contract = contract(required=True, scope="session")

    first = resolve_scoped_external_context(
        scoped_contract,
        {"customer_id": "cus-1"},
        session_snapshot=None,
    )

    with pytest.raises(ExternalContextContractError, match="cannot be supplied again"):
        resolve_scoped_external_context(
            scoped_contract,
            {"customer_id": "cus-1"},
            session_snapshot=first.session_snapshot,
        )


def test_scoped_resolution_rejects_session_snapshot_after_scope_change() -> None:
    previous_session_snapshot = {"customer_id": "cus-1"}
    changed_contract = contract(required=False, scope="run")

    with pytest.raises(
        ExternalContextContractError,
        match="no longer satisfies the active contract",
    ):
        resolve_scoped_external_context(
            changed_contract,
            {},
            session_snapshot=previous_session_snapshot,
        )
