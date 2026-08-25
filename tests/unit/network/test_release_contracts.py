from types import SimpleNamespace

from modules.agent.domain.release_versioning import (
    ReleaseChangeKind,
    calculate_next_release_version,
)
from modules.network.application.release_lifecycle import _next_staging_version
from modules.network.domain.release_contracts import (
    agent_snapshot_hash,
    canonical_hash,
    classify_contract_change,
    output_contract_snapshot,
)


def release(**overrides):
    values = {
        "prompt_version_id": None,
        "contract_version_id": None,
        "knowledge_version_id": None,
        "model_config_version_id": None,
        "provider_model_id": None,
        "fallback_provider_model_id": None,
        "name": "Support Agent",
        "description": "",
        "system_prompt": "Help the user.",
        "response_format": None,
        "output_schema": None,
        "provider": "openrouter",
        "model": "test-model",
        "provider_credential_id": None,
        "fallback_provider": None,
        "fallback_model": None,
        "fallback_credential_id": None,
        "base_url": None,
        "temperature": 0.2,
        "max_output_tokens": 512,
        "session_mode": "stateful",
        "agent_status": "active",
        "collection_ids": [],
        "runtime_config": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def contract(properties, required=None):
    return {
        "enabled": True,
        "type": "json",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required or [],
        },
    }


def test_agent_snapshot_hash_ignores_lifecycle_metadata() -> None:
    first = release()
    second = release()
    first.id = "release-a"
    second.id = "release-b"
    first.version = "v1.0.20260715.01"
    second.version = "v2.0.20260715.01"
    first.status = "staging"
    second.status = "production"

    assert agent_snapshot_hash(first) == agent_snapshot_hash(second)


def test_output_contract_is_inherited_from_entry_release() -> None:
    snapshot = output_contract_snapshot(
        release(
            response_format=contract(
                {"answer": {"type": "string"}},
                required=["answer"],
            )
        )
    )

    assert snapshot is not None
    assert snapshot["type"] == "json"
    assert snapshot["strict"] is True
    assert snapshot["schema"]["required"] == ["answer"]


def test_network_contract_change_uses_entry_contract_compatibility() -> None:
    previous = contract(
        {
            "answer": {"type": "string"},
            "confidence": {"type": "number"},
        },
        required=["answer"],
    )
    feature = contract(
        {
            "answer": {"type": "string"},
            "confidence": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["answer"],
    )
    incompatible = contract(
        {"answer": {"type": "number"}},
        required=["answer"],
    )

    assert classify_contract_change(previous, feature) == ReleaseChangeKind.FEATURE
    assert (
        classify_contract_change(previous, incompatible)
        == ReleaseChangeKind.COMPATIBILITY
    )
    assert classify_contract_change(previous, previous) == ReleaseChangeKind.CHANGE


def test_network_release_uses_agent_semantic_version_format() -> None:
    assert (
        calculate_next_release_version([], ReleaseChangeKind.CHANGE)
        .startswith("v0.0.")
    )
    assert calculate_next_release_version(
        ["v1.2.20260715.01"],
        ReleaseChangeKind.FEATURE,
    ).startswith("v1.3.")
    assert calculate_next_release_version(
        ["v1.2.20260715.01"],
        ReleaseChangeKind.COMPATIBILITY,
    ).startswith("v2.0.")


def test_staging_versions_have_independent_revision_sequence() -> None:
    assert _next_staging_version([]) == "staging-r1"
    assert _next_staging_version(["staging-r1", "staging-r4"]) == "staging-r5"
    assert _next_staging_version(["v2.20260715.171529"]) == "staging-r1"


def test_canonical_hash_does_not_depend_on_dictionary_order() -> None:
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})
