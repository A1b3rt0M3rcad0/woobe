from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from modules.evaluation.application.evaluation_protocol import evaluation_protocol_hash
from modules.evaluation.application.run_judge import (
    clean_suite_judge_config,
    judge_summary_from_run,
    selected_judge_config,
    selected_judge_provider_model_id,
)


def _suite(default_judge_id):
    return SimpleNamespace(
        id=uuid4(),
        dataset_version_id=uuid4(),
        judge_provider_model_id=default_judge_id,
        judge_config={"max_tokens": 1200},
        rubric={"judge_weight": 4},
        deterministic_checks={"enabled": True},
        acceptance_policy={"minimum_score": 70},
        suite_hash="suite-hash",
    )


def test_run_override_selects_frozen_judge_and_config() -> None:
    suite_judge_id = uuid4()
    run_judge_id = uuid4()
    run = SimpleNamespace(
        execution_policy={
            "judge_protocol": {
                "source": "run_override",
                "judge_provider_model_id": str(run_judge_id),
                "normalized_judge_config": {"max_tokens": 2048, "attempts": 3},
                "judge_model_snapshot": {
                    "provider_model_id": str(run_judge_id),
                    "display_name": "Run Judge",
                    "provider": "openrouter",
                    "model": "vendor/model",
                    "credential_name": "Primary",
                    "capabilities": {"response_strategy": "json_object"},
                    "snapshot_hash": "judge-snapshot",
                },
            }
        },
        aggregate_result={},
    )

    assert selected_judge_provider_model_id(run, suite_judge_id) == run_judge_id
    assert selected_judge_config(run, {"max_tokens": 1200}) == {
        "max_tokens": 2048,
        "attempts": 3,
    }
    assert judge_summary_from_run(run) == {
        "provider_model_id": str(run_judge_id),
        "display_name": "Run Judge",
        "provider": "openrouter",
        "model": "vendor/model",
        "credential_name": "Primary",
        "response_strategy": "json_object",
        "snapshot_hash": "judge-snapshot",
        "source": "run_override",
    }


def test_clean_suite_config_removes_stale_governance_snapshot() -> None:
    assert clean_suite_judge_config(
        {
            "max_tokens": 1200,
            "judge_model_snapshot": {"model": "old"},
            "judge_model_snapshot_hash": "old-hash",
            "judge_protocol_version": "old-protocol",
        }
    ) == {"max_tokens": 1200}


def test_protocol_hash_changes_when_run_uses_another_judge() -> None:
    suite_judge_id = uuid4()
    override_judge_id = uuid4()
    suite = _suite(suite_judge_id)

    default_hash = evaluation_protocol_hash(suite)
    override_hash = evaluation_protocol_hash(
        suite,
        judge_provider_model_id=override_judge_id,
        judge_config={"max_tokens": 2048},
        judge_model_snapshot_hash="override-snapshot",
    )

    assert override_hash != default_hash
