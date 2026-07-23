from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from modules.evaluation.infra.runtime_safe_judge import (
    is_null_score_contract_error,
    sanitize_judge_config,
)
from modules.evaluation.infra.workers.run_judge_worker import effective_suite_for_run


def test_null_score_type_error_is_recognized_as_structured_contract_failure() -> None:
    assert is_null_score_contract_error(
        "judge_failed: TypeError: float() argument must be a string or a real number, not 'NoneType'"
    ) is True


def test_explicit_null_optional_judge_settings_fall_back_to_defaults() -> None:
    assert sanitize_judge_config(
        {
            "temperature": None,
            "timeout_seconds": None,
            "maximum_cost_usd": None,
            "max_tokens": 1200,
            "reasoning_policy": "provider_default",
        }
    ) == {
        "max_tokens": 1200,
        "reasoning_policy": "provider_default",
    }


def test_effective_suite_uses_judge_frozen_on_run_without_mutating_suite() -> None:
    suite_judge_id = uuid4()
    run_judge_id = uuid4()
    suite = SimpleNamespace(
        judge_provider_model_id=suite_judge_id,
        judge_config={"max_tokens": 1200},
        rubric={"judge_weight": 4},
        deterministic_checks={"enabled": True},
    )
    run = SimpleNamespace(
        execution_policy={
            "judge_protocol": {
                "source": "run_override",
                "judge_provider_model_id": str(run_judge_id),
                "normalized_judge_config": {
                    "max_tokens": 2048,
                    "attempts": 3,
                },
            }
        }
    )

    effective = effective_suite_for_run(run, suite)

    assert effective.judge_provider_model_id == run_judge_id
    assert effective.judge_config == {"max_tokens": 2048, "attempts": 3}
    assert effective.rubric == suite.rubric
    assert effective.deterministic_checks == suite.deterministic_checks
    assert suite.judge_provider_model_id == suite_judge_id
    assert suite.judge_config == {"max_tokens": 1200}
