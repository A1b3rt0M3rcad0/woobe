from __future__ import annotations

from modules.agent.domain.external_context_contract import compose_external_context_contracts
from modules.network.infra.runtime.loader import NetworkRuntimeLoader


_NETWORK_EXTERNAL_CONTEXT_OVERRIDE_KEY = "__network_external_context__"


def _field(*, field_type: str, expose: bool) -> dict:
    return {
        "schema": {"type": field_type},
        "required": True,
        "model": {"expose": expose},
    }


def test_runtime_loader_projects_only_fields_declared_by_each_network_consumer() -> None:
    root = "root-node"
    specialist = "specialist-node"
    effective = compose_external_context_contracts(
        {
            root: {
                "age": _field(field_type="integer", expose=False),
                "name": _field(field_type="string", expose=True),
            },
            specialist: {
                "customer_id": _field(field_type="string", expose=False),
            },
        }
    )
    bindings = {
        root: {"snapshot_override": {"provider": "custom", "model": "root-model"}},
        specialist: {
            "snapshot_override": {"provider": "custom", "model": "specialist-model"}
        },
    }

    bound = NetworkRuntimeLoader._bind_external_context(
        bindings,
        effective,
        {
            "age": 18,
            "name": "Alberto",
            "customer_id": "cus-123",
        },
    )

    assert bound[root]["snapshot_override"][_NETWORK_EXTERNAL_CONTEXT_OVERRIDE_KEY] == {
        "age": 18,
        "name": "Alberto",
    }
    assert bound[specialist]["snapshot_override"][
        _NETWORK_EXTERNAL_CONTEXT_OVERRIDE_KEY
    ] == {"customer_id": "cus-123"}


def test_runtime_loader_keeps_hidden_fields_for_agent_runtime_even_when_model_cannot_see_them() -> None:
    node = "root-node"
    effective = compose_external_context_contracts(
        {
            node: {
                "age": _field(field_type="integer", expose=False),
                "name": _field(field_type="string", expose=True),
            }
        }
    )

    bound = NetworkRuntimeLoader._bind_external_context(
        {node: {"snapshot_override": {}}},
        effective,
        {"age": 18, "name": "Alberto"},
    )

    # Network projects the complete Agent contract. The Agent resolver later derives
    # model_external_context from model.expose while hidden values remain available to
    # trusted Tool bindings.
    assert bound[node]["snapshot_override"][_NETWORK_EXTERNAL_CONTEXT_OVERRIDE_KEY] == {
        "age": 18,
        "name": "Alberto",
    }
