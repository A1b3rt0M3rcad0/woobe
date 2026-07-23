from __future__ import annotations

from modules.evaluation.infra.adaptive_judge import (
    is_output_length_error,
    is_reasoning_model,
    judge_inference_profiles,
    judge_output_token_limit,
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
    ) == 1600


def test_fixed_policy_preserves_explicit_budget() -> None:
    assert recommended_judge_output_tokens(
        "custom/model",
        {},
        {"output_budget_policy": "fixed", "max_tokens": 1800},
    ) == 1800


def test_reasoning_metadata_enables_reasoning_budget() -> None:
    assert is_reasoning_model("custom/model", {"supports_reasoning": True}) is True


def test_openrouter_judge_disables_reasoning_by_default() -> None:
    profiles = judge_inference_profiles(
        "openrouter",
        "deepseek/deepseek-v4-flash",
        {},
        None,
        {},
    )

    assert profiles[0] == (
        "openrouter_reasoning_none",
        {"reasoning": {"effort": "none", "exclude": True}},
    )
    assert profiles[-1] == ("provider_default", None)


def test_custom_deepseek_judge_has_controlled_fallbacks() -> None:
    profiles = judge_inference_profiles(
        "custom",
        "deepseek/deepseek-v4-flash",
        {},
        "https://api.deepseek.com/v1",
        {},
    )

    assert profiles[0] == (
        "deepseek_thinking_disabled",
        {"thinking": {"type": "disabled"}},
    )
    assert profiles[1][0] == "unified_reasoning_none"
    assert profiles[-1] == ("provider_default", None)


def test_non_reasoning_model_keeps_provider_default_inference() -> None:
    assert judge_inference_profiles(
        "openai",
        "gpt-4.1-mini",
        {},
        None,
        {},
    ) == [("provider_default", None)]


def test_reasoning_model_uses_declared_output_ceiling() -> None:
    assert judge_output_token_limit(
        "custom/reasoning-model",
        {
            "supports_reasoning": True,
            "max_output_tokens": 24_000,
        },
    ) == 24_000


def test_reasoning_model_without_metadata_uses_safe_ceiling() -> None:
    assert judge_output_token_limit("deepseek/deepseek-v4-flash", {}) == 16_384


def test_declared_output_ceiling_is_bounded_for_evaluation_cost_safety() -> None:
    assert judge_output_token_limit(
        "custom/model",
        {"max_completion_tokens": 100_000},
    ) == 32_768


def test_length_finish_reason_error_is_retryable_signal() -> None:
    error = LengthFinishReasonError(
        "Could not parse response content as the length limit was reached - "
        "CompletionUsage(completion_tokens=801, prompt_tokens=1947, "
        "completion_tokens_details=CompletionTokensDetails(reasoning_tokens=800))"
    )

    assert is_output_length_error(error) is True


def test_unrelated_validation_error_is_not_length_signal() -> None:
    assert is_output_length_error(ValueError("Judge score must be numeric") is False)
