from __future__ import annotations

import pytest

from modules.agent.domain.external_context_contract import (
    ExternalContextContractError,
    compose_external_context_contracts,
)
from modules.network.domain.external_context_contract import (
    consumer_external_context_contract,
    project_effective_external_context,
    resolve_effective_external_context,
)


def _field(
    *,
    required: bool,
    expose: bool,
    default: str | None = None,
    description: str | None = None,
) -> dict:
    field = {
        "schema": {"type": "string"},
        "required": required,
        "scope": "session",
        "model": {"expose": expose},
    }
    if default is not None:
        field["default"] = default
    if description is not None:
        field["description"] = description
    return field


def test_same_network_field_preserves_consumer_specific_required_and_model_visibility() -> None:
    effective = compose_external_context_contracts(
        {
            "root": {
                "customer_id": _field(required=True, expose=True),
            },
            "specialist": {
                "customer_id": _field(required=False, expose=False),
            },
        }
    )

    root = consumer_external_context_contract(effective, "root")
    specialist = consumer_external_context_contract(effective, "specialist")

    assert root["customer_id"]["required"] is True
    assert root["customer_id"]["model"]["expose"] is True
    assert specialist["customer_id"]["required"] is False
    assert specialist["customer_id"]["model"]["expose"] is False


def test_network_acceptance_defers_required_validation_until_consumer_invocation() -> None:
    effective = compose_external_context_contracts(
        {
            "root": {
                "customer_id": _field(required=False, expose=False),
            },
            "specialist": {
                "customer_id": _field(required=True, expose=False),
            },
        }
    )

    accepted = resolve_effective_external_context(effective, {})

    assert accepted.snapshot == {}
    assert project_effective_external_context(
        effective,
        "root",
        accepted.snapshot,
    ) == {}

    with pytest.raises(
        ExternalContextContractError,
        match="Required External Context field is missing: customer_id",
    ):
        project_effective_external_context(
            effective,
            "specialist",
            accepted.snapshot,
        )


def test_network_defaults_remain_consumer_specific_for_the_same_field() -> None:
    effective = compose_external_context_contracts(
        {
            "root": {
                "locale": _field(
                    required=True,
                    expose=True,
                    default="pt-BR",
                ),
            },
            "specialist": {
                "locale": _field(
                    required=True,
                    expose=False,
                    default="en-US",
                ),
            },
        }
    )

    assert project_effective_external_context(effective, "root", {}) == {
        "locale": "pt-BR"
    }
    assert project_effective_external_context(effective, "specialist", {}) == {
        "locale": "en-US"
    }


def test_network_consumer_reconstruction_preserves_field_description() -> None:
    effective = compose_external_context_contracts(
        {
            "root": {
                "name": _field(
                    required=True,
                    expose=True,
                    description="Authenticated customer name.",
                )
            }
        }
    )

    root = consumer_external_context_contract(effective, "root")

    assert root["name"]["description"] == "Authenticated customer name."


def test_session_value_update_is_reused_by_next_network_run() -> None:
    effective = compose_external_context_contracts(
        {
            "root": {
                "name": _field(required=True, expose=True),
            }
        }
    )

    first = resolve_effective_external_context(
        effective,
        {"name": "Alberto"},
        session_values={"name": "Old Name"},
    )
    second = resolve_effective_external_context(
        effective,
        {},
        session_values=first.session_values,
    )

    assert first.snapshot == {"name": "Alberto"}
    assert first.session_values == {"name": "Alberto"}
    assert second.snapshot == {"name": "Alberto"}
    assert second.session_values == {"name": "Alberto"}
