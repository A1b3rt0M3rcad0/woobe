from __future__ import annotations

from uuid import uuid4

from shared.security.tenancy import TenantAuthorizer


def test_agent_evaluation_target_remaps_version_id_away_from_prompt_versions() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    release_id = uuid4()
    provider_model_id = uuid4()

    identifiers = TenantAuthorizer._identifiers(
        {"project_id": str(project_id)},
        {},
        {
            "target": {
                "target_type": "agent",
                "source_type": "release",
                "entity_id": str(agent_id),
                "version_id": str(release_id),
            },
            "generator_provider_model_id": str(provider_model_id),
        },
    )

    assert ("project_id", str(project_id)) in identifiers
    assert ("agent_id", str(agent_id)) in identifiers
    assert ("target_version_id", str(release_id)) in identifiers
    assert ("generator_provider_model_id", str(provider_model_id)) in identifiers
    assert ("version_id", str(release_id)) not in identifiers


def test_network_evaluation_target_uses_network_tenancy_keys() -> None:
    network_id = uuid4()
    network_version_id = uuid4()

    identifiers = TenantAuthorizer._identifiers(
        {},
        {},
        {
            "candidate": {
                "target_type": "network",
                "source_type": "staging",
                "entity_id": str(network_id),
                "version_id": str(network_version_id),
            }
        },
    )

    assert ("network_id", str(network_id)) in identifiers
    assert ("target_version_id", str(network_version_id)) in identifiers
    assert ("version_id", str(network_version_id)) not in identifiers


def test_non_evaluation_version_id_remains_prompt_version_identifier() -> None:
    prompt_version_id = uuid4()

    identifiers = TenantAuthorizer._identifiers(
        {"version_id": str(prompt_version_id)},
        {},
        None,
    )

    assert identifiers == [("version_id", str(prompt_version_id))]
