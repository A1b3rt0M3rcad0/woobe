from __future__ import annotations

import pytest

from modules.agent.domain.external_context_contract import (
    ExternalContextContractError,
    compose_external_context_contracts,
)
from modules.agent.domain.release_versioning import ReleaseChangeKind
from modules.network.domain.external_context_contract import (
    classify_effective_external_context_change,
    project_effective_external_context,
    resolve_effective_external_context,
)


def agent_contract(
    *,
    required: bool = False,
    scope: str = "run",
    expose: bool = False,
    default: str | None = None,
):
    field = {
        "schema": {"type": "string"},
        "required": required,
        "scope": scope,
        "model": {"expose": expose},
    }
    if default is not None:
        field["default"] = default
    return {"customer_id": field}


def test_effective_resolution_reuses_only_session_values() -> None:
    effective = compose_external_context_contracts(
        {"support": agent_contract(scope="session")}
    )
    first = resolve_effective_external_context(
        effective,
        {"customer_id": "cus-1"},
    )
    assert first.snapshot == {"customer_id": "cus-1"}
    assert first.session_values == {"customer_id": "cus-1"}

    second = resolve_effective_external_context(
        effective,
        {},
        session_values=first.session_values,
    )
    assert second.snapshot == {"customer_id": "cus-1"}

    run_effective = compose_external_context_contracts(
        {"support": agent_contract(scope="run")}
    )
    run_second = resolve_effective_external_context(
        run_effective,
        {},
        session_values={"customer_id": "must-not-leak"},
    )
    assert run_second.snapshot == {}
    assert run_second.session_values == {}


def test_effective_resolution_rejects_undeclared_values() -> None:
    effective = compose_external_context_contracts({"support": agent_contract()})
    with pytest.raises(ExternalContextContractError, match="undeclared"):
        resolve_effective_external_context(effective, {"unknown": "value"})


def test_projection_is_consumer_scoped_and_applies_default() -> None:
    support = {
        "customer_id": {
            "schema": {"type": "string"},
            "required": True,
            "scope": "run",
            "default": "anonymous",
            "model": {"expose": False},
        }
    }
    orders = {
        "order_id": {
            "schema": {"type": "string"},
            "required": False,
            "scope": "run",
            "model": {"expose": False},
        }
    }
    effective = compose_external_context_contracts(
        {"support": support, "orders": orders}
    )

    assert project_effective_external_context(
        effective,
        "support",
        {"order_id": "ord-1"},
    ) == {"customer_id": "anonymous"}
    assert project_effective_external_context(
        effective,
        "orders",
        {"customer_id": "cus-1", "order_id": "ord-1"},
    ) == {"order_id": "ord-1"}


def test_effective_contract_add_optional_field_is_feature() -> None:
    previous = compose_external_context_contracts({})
    candidate = compose_external_context_contracts(
        {"support": agent_contract(required=False)}
    )
    assert (
        classify_effective_external_context_change(previous, candidate)
        is ReleaseChangeKind.FEATURE
    )


def test_effective_contract_add_required_field_breaks_compatibility() -> None:
    previous = compose_external_context_contracts({})
    candidate = compose_external_context_contracts(
        {"support": agent_contract(required=True)}
    )
    assert (
        classify_effective_external_context_change(previous, candidate)
        is ReleaseChangeKind.COMPATIBILITY
    )


def test_effective_contract_remove_field_breaks_strict_boundary() -> None:
    previous = compose_external_context_contracts(
        {"support": agent_contract(required=False)}
    )
    candidate = compose_external_context_contracts({})
    assert (
        classify_effective_external_context_change(previous, candidate)
        is ReleaseChangeKind.COMPATIBILITY
    )


def test_existing_consumer_optional_to_required_breaks_compatibility() -> None:
    previous = compose_external_context_contracts(
        {"support": agent_contract(required=False)}
    )
    candidate = compose_external_context_contracts(
        {"support": agent_contract(required=True)}
    )
    assert (
        classify_effective_external_context_change(previous, candidate)
        is ReleaseChangeKind.COMPATIBILITY
    )
