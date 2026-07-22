from __future__ import annotations

from modules.evaluation.infra.adaptive_judge import (
    is_output_length_error,
    is_reasoning_model,
    recommended_judge_output_tokens,
)


class LengthFinishReasonError(RuntimeError):
    pass


def test_reasoning_model_replaces_legacy_800_token_budget() -> None:
    assert is_reasoning_model("deepseek/deepseek-v4-flash", {}) is True
    assert recommended_judge_output_tokens(
        "deepseek/deepseek-v4-flash",
        {},
        {"max_tokens": 800},
    ) >= 3000


def test_non_reasoning_model_receives_safe_minimum_budget() -> None:
    assert is_reasoning_model("openai/gpt-4.1-mini", {}) is False
    assert recommended_judge_output_tokens(
        "openai/gpt-4.1-mini",
        {},
        {"max_tokens": 800},
    ) == 1200


def test_fixed_policy_preserves_explicit_budget() -> None:
    assert recommended_judge_output_tokens(
        "custom/model",
        {},
        {"output_budget_policy": "fixed", "max_tokens": 1800},
    ) == 1800


def test_reasoning_metadata_enables_reasoning_budget() -> None:
    assert is_reasoning_model("custom/model", {"supports_reasoning": True}) is True


def test_length_finish_reason_error_is_retryable_signal() -> None:
    error = LengthFinishReasonError(
        "Could not parse response content as the length limit was reached - "
        "CompletionUsage(completion_tokens=801, prompt_tokens=1947, "
        "completion_tokens_details=CompletionTokensDetails(reasoning_tokens=800))"
    )

    assert is_output_length_error(error) is True


def test_unrelated_validation_error_is_not_length_signal() -> None:
    assert is_output_length_error(ValueError("Judge score must be numeric")) is False
