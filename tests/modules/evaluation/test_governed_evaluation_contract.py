from __future__ import annotations

from types import SimpleNamespace

from modules.evaluation.application.experience_service import _safe_preview_target
from modules.evaluation.application.human_decision_service import (
    _assessment_status,
    _target_manifest,
)
from modules.evaluation.infra.workers.governed_worker import _policy_assessment


def test_policy_assessment_is_not_a_human_decision() -> None:
    assert _policy_assessment("qualified") == "meets_policy"
    assert _policy_assessment("qualified_with_warnings") == "meets_policy"
    assert _policy_assessment("not_qualified") == "below_policy"
    assert _policy_assessment("inconclusive") == "inconclusive"


def test_legacy_qualification_is_read_as_assessment_only() -> None:
    assert _assessment_status(
        SimpleNamespace(aggregate_result={}, qualification_status="qualified")
    ) == "meets_policy"
    assert _assessment_status(
        SimpleNamespace(aggregate_result={}, qualification_status="not_qualified")
    ) == "below_policy"


def test_agent_manifest_excludes_provider_credentials() -> None:
    target = SimpleNamespace(
        target_type="agent",
        display_name="Calculator",
        environment="production",
        display_version="v1",
        snapshot_hash="abc",
        composition_hash=None,
        agent_release_id="release-id",
        network_version_id=None,
        snapshot={
            "provider": "provider",
            "model": "model",
            "provider_model_id": "model-id",
            "provider_credential_id": "secret-credential-id",
            "base_url": "https://provider.invalid",
            "system_prompt": "private prompt",
            "runtime_config": {"tools": {"snapshots": []}},
            "collection_ids": [],
        },
    )

    manifest = _target_manifest(target)

    assert manifest["model"]["provider"] == "provider"
    assert "provider_credential_id" not in manifest["model"]
    assert "base_url" not in manifest["model"]
    assert "private prompt" not in str(manifest)


def test_preview_target_does_not_return_raw_snapshot() -> None:
    payload = _safe_preview_target(
        {
            "target_type": "agent",
            "source_type": "release",
            "entity_id": "00000000-0000-0000-0000-000000000001",
            "environment": "production",
            "agent_release_id": "00000000-0000-0000-0000-000000000002",
            "network_version_id": None,
            "snapshot": {
                "provider": "provider",
                "model": "model",
                "provider_credential_id": "credential-secret",
                "runtime_config": {},
            },
            "snapshot_hash": "snapshot-hash",
            "composition_hash": None,
            "display_name": "Agent",
            "display_version": "v1",
        }
    )

    assert payload is not None
    assert "snapshot" not in payload
    assert "credential-secret" not in str(payload)
    assert payload["manifest"]["model"]["model"] == "model"
