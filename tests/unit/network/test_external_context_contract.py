from __future__ import annotations

import pytest

from modules.agent.domain.external_context_contract import (
    ExternalContextContractError,
    ExternalContextSessionConflict,
    compose_external_context_contracts,
)
from modules.agent.domain.release_versioning import ReleaseChangeKind
from modules.network.domain.external_context_contract import (
    classify_effective_external_context_change,
    project_effective_external_context,
    resolve_effective_external_context,
    resolve_scoped_effective_external_context,
)


def agent_contract(
    *,
    required: bool = False,
    expose: bool = False,
    default: str | None = None,
    scope: str = "run",
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


def test_effective_resolution_is_run_local() -> None:
    effective = compose_external_context_contracts(
        {"support": agent_contract(required=False)}
    )
    first = resolve_effective_external_context(
        effective,
        {"customer_id": "cus-1"},
    )
    second = resolve_effective_external_context(effective, {})

    assert first.snapshot == {"customer_id": "cus-1"}
    assert second.snapshot == {}


def test_effective_resolution_rejects_undeclared_values() -> None:
    effective = compose_external_context_contracts({"support": agent_contract()})
    with pytest.raises(ExternalContextContractError, match="undeclared"):
        resolve_effective_external_context(effective, {"unknown": "value"})


def test_projection_is_consumer_scoped_and_applies_default() -> None:
    support = {
        "customer_id": {
            "schema": {"type": "string"},
            "required": True,
            "default": "anonymous",
            "model": {"expose": False},
        }
    }
    orders = {
        "order_id": {
            "schema": {"type": "string"},
            "required": False,
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


def test_effective_session_scope_is_initialized_once_and_merged_with_run_scope() -> None:
    effective = compose_external_context_contracts(
        {
            "support": {
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
                    "model": {"expose": False},
                },
            }
        }
    )

    first = resolve_scoped_effective_external_context(
        effective,
        {"customer_id": "cus-1", "current_page": "/checkout"},
        session_snapshot=None,
    )
    second = resolve_scoped_effective_external_context(
        effective,
        {"current_page": "/orders"},
        session_snapshot=first.session_snapshot,
    )

    assert first.session_snapshot == {"customer_id": "cus-1"}
    assert first.run_snapshot == {"current_page": "/checkout"}
    assert second.snapshot == {
        "customer_id": "cus-1",
        "current_page": "/orders",
    }


def test_effective_session_scope_rejects_repeated_input() -> None:
    effective = compose_external_context_contracts(
        {"support": agent_contract(required=True, scope="session")}
    )
    first = resolve_scoped_effective_external_context(
        effective,
        {"customer_id": "cus-1"},
        session_snapshot=None,
    )

    with pytest.raises(ExternalContextContractError, match="cannot be supplied again"):
        resolve_scoped_effective_external_context(
            effective,
            {"customer_id": "cus-1"},
            session_snapshot=first.session_snapshot,
        )


def test_fixed_network_session_field_conflicts_before_revalidating_replayed_value() -> None:
    effective = compose_external_context_contracts(
        {"support": agent_contract(required=True, scope="session")}
    )

    with pytest.raises(ExternalContextSessionConflict) as exc_info:
        resolve_scoped_effective_external_context(
            effective,
            {"customer_id": 123},
            session_snapshot={"customer_id": "cus-1"},
        )

    assert exc_info.value.code == "EXTERNAL_CONTEXT_SESSION_FIELD_ALREADY_SET"
    assert exc_info.value.fields == ["customer_id"]


def test_network_session_fields_are_write_once_per_field() -> None:
    effective = compose_external_context_contracts(
        {
            "support": {
                "customer_id": {
                    "schema": {"type": "string"},
                    "required": True,
                    "scope": "session",
                    "model": {"expose": False},
                },
                "country": {
                    "schema": {"type": "string"},
                    "required": False,
                    "scope": "session",
                    "model": {"expose": False},
                },
                "page": {
                    "schema": {"type": "string"},
                    "required": True,
                    "scope": "run",
                    "model": {"expose": False},
                },
            }
        }
    )

    first = resolve_scoped_effective_external_context(
        effective,
        {"customer_id": "cus-1", "page": "/home"},
        session_snapshot=None,
    )
    assert first.session_snapshot == {"customer_id": "cus-1"}

    second = resolve_scoped_effective_external_context(
        effective,
        {"country": "BR", "page": "/billing"},
        session_snapshot=first.session_snapshot,
    )
    assert second.session_snapshot == {
        "customer_id": "cus-1",
        "country": "BR",
    }

    with pytest.raises(ExternalContextSessionConflict) as exc_info:
        resolve_scoped_effective_external_context(
            effective,
            {"customer_id": "cus-1", "page": "/orders"},
            session_snapshot=second.session_snapshot,
        )

    assert exc_info.value.code == "EXTERNAL_CONTEXT_SESSION_FIELD_ALREADY_SET"


def test_effective_scope_change_is_compatibility_break() -> None:
    previous = compose_external_context_contracts(
        {"support": agent_contract(scope="run")}
    )
    candidate = compose_external_context_contracts(
        {"support": agent_contract(scope="session")}
    )

    assert (
        classify_effective_external_context_change(previous, candidate)
        is ReleaseChangeKind.COMPATIBILITY
    )


def test_effective_resolution_rejects_stale_session_snapshot_after_scope_change() -> None:
    changed = compose_external_context_contracts(
        {"support": agent_contract(scope="run")}
    )

    with pytest.raises(
        ExternalContextContractError,
        match="no longer satisfies the active contract",
    ):
        resolve_scoped_effective_external_context(
            changed,
            {},
            session_snapshot={"customer_id": "cus-1"},
        )
