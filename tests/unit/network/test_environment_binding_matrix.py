from uuid import uuid4

import pytest

from modules.network.domain.entities import (
    AgentBindingSelector,
    NetworkDefinition,
    NetworkLimits,
    NetworkNode,
)
from modules.network.domain.environment_bindings import (
    NetworkEnvironmentBindingError,
    validate_network_environment_bindings,
)


def definition_with(source: str) -> NetworkDefinition:
    node_id = uuid4()
    return NetworkDefinition(
        schema_version=2,
        root_node_id=node_id,
        nodes=(
            NetworkNode(
                id=node_id,
                agent_id=uuid4(),
                label="Agent",
                capability_description="Respond",
                position={"x": 0, "y": 0},
                binding=AgentBindingSelector(
                    source=source,
                    release_id=None if source == "draft" else uuid4(),
                ),
            ),
        ),
        edges=(),
        limits=NetworkLimits(
            max_depth=2,
            max_invocations=8,
            timeout_seconds=30,
        ),
        session_mode="stateful",
    )


@pytest.mark.parametrize("source", ["draft", "staging", "release"])
def test_network_draft_accepts_all_binding_sources(source):
    validate_network_environment_bindings(definition_with(source), "draft")


@pytest.mark.parametrize("source", ["staging", "release"])
def test_network_staging_accepts_staging_or_release(source):
    validate_network_environment_bindings(definition_with(source), "staging")


def test_network_staging_rejects_draft():
    with pytest.raises(NetworkEnvironmentBindingError):
        validate_network_environment_bindings(definition_with("draft"), "staging")


def test_network_production_accepts_only_release():
    validate_network_environment_bindings(definition_with("release"), "production")
    for source in ("draft", "staging"):
        with pytest.raises(NetworkEnvironmentBindingError):
            validate_network_environment_bindings(
                definition_with(source),
                "production",
            )
