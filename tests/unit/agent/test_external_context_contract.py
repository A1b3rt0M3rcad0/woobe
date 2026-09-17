from __future__ import annotations

import pytest

from modules.agent.domain.external_context_contract import (
    ExternalContextContractError,
    classify_external_context_change,
    compose_external_context_contracts,
    normalize_external_context_contract,
    project_external_context,
    resolve_external_context,
    validate_effective_external_context_values,
)
from modules.agent.domain.release_versioning import ReleaseChangeKind


def contract(*, required: bool = False, scope: str = "run", expose: bool = False):
    return {
        "customer_id": {
            "schema": {"type": "string"},
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


def test_unknown_request_fields_are_rejected() -> None:
    with pytest.raises(ExternalContextContractError, match="undeclared fields"):
        resolve_external_context(contract(), {"unknown": "value"})


def test_required_field_is_enforced() -> None:
    with pytest.raises(ExternalContextContractError, match="customer_id"):
        resolve_external_context(contract(required=True), {})


def test_session_scope_reuses_and_updates_session_value() -> None:
    first = resolve_external_context(
        contract(required=True, scope="session"),
        {"customer_id": "cus-1"},
    )
    assert first.snapshot == {"customer_id": "cus-1"}
    assert first.session_values == {"customer_id": "cus-1"}

    second = resolve_external_context(
        contract(required=True, scope="session"),
        {},
        session_values=first.session_values,
    )
    assert second.snapshot == {"customer_id": "cus-1"}


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


def test_scope_change_breaks_compatibility() -> None:
    assert (
        classify_external_context_change(
            contract(scope="session"),
            contract(scope="run"),
        )
        == ReleaseChangeKind.COMPATIBILITY
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


def test_network_contract_rejects_semantic_conflicts() -> None:
    with pytest.raises(ExternalContextContractError, match="conflicts"):
        compose_external_context_contracts(
            {
                "support": contract(scope="session"),
                "orders": contract(scope="run"),
            }
        )


def test_effective_network_boundary_is_strict_but_defers_required_to_consumer() -> None:
    effective = compose_external_context_contracts(
        {"orders": contract(required=True)}
    )
    assert validate_effective_external_context_values(effective, {}) == {}
    with pytest.raises(ExternalContextContractError, match="undeclared"):
        validate_effective_external_context_values(effective, {"unknown": 1})
