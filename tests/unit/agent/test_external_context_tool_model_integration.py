from __future__ import annotations

from modules.agent.application.tool_context_bindings import apply_context_bindings
from modules.agent.domain.external_context_contract import (
    model_external_context,
    resolve_external_context,
)


def _binding(field: str) -> dict:
    return {"source": {"kind": "context", "field": field}}


def test_hidden_session_context_is_available_to_tool_binding_but_not_to_model() -> None:
    contract = {
        "tenant_id": {
            "schema": {"type": "string"},
            "required": True,
            "scope": "session",
            "model": {"expose": False},
        },
        "name": {
            "schema": {"type": "string"},
            "required": True,
            "scope": "session",
            "model": {"expose": True},
        },
    }
    resolved = resolve_external_context(
        contract,
        {
            "tenant_id": "tenant-123",
            "name": "Alberto",
        },
    )

    assert model_external_context(contract, resolved.snapshot) == {
        "name": "Alberto"
    }

    tool_input = apply_context_bindings(
        {"bindings": {"tenant_id": _binding("tenant_id")}},
        {"query": "recent orders"},
        resolved.snapshot,
    )

    assert tool_input == {
        "query": "recent orders",
        "tenant_id": "tenant-123",
    }


def test_hidden_session_context_remains_available_to_tool_on_next_run_without_resend() -> None:
    contract = {
        "tenant_id": {
            "schema": {"type": "string"},
            "required": True,
            "scope": "session",
            "model": {"expose": False},
        }
    }
    first = resolve_external_context(
        contract,
        {"tenant_id": "tenant-123"},
    )
    second = resolve_external_context(
        contract,
        {},
        session_values=first.session_values,
    )

    assert model_external_context(contract, second.snapshot) == {}
    assert apply_context_bindings(
        {"bindings": {"tenant_id": _binding("tenant_id")}},
        {},
        second.snapshot,
    ) == {"tenant_id": "tenant-123"}


def test_run_scoped_hidden_tool_context_is_not_recovered_from_session_on_next_run() -> None:
    contract = {
        "request_id": {
            "schema": {"type": "string"},
            "required": False,
            "scope": "run",
            "model": {"expose": False},
        }
    }
    first = resolve_external_context(
        contract,
        {"request_id": "req-1"},
    )
    second = resolve_external_context(
        contract,
        {},
        session_values=first.session_values,
    )

    assert first.snapshot == {"request_id": "req-1"}
    assert second.snapshot == {}
