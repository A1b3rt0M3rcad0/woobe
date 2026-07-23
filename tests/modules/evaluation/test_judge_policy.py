from __future__ import annotations

from modules.evaluation.application.judge_policy import (
    explicit_reasoning_support,
    judge_response_strategy,
    normalized_judge_config,
    resolve_judge_budget,
)


def test_configured_judge_budget_is_never_raised_to_model_ceiling() -> None:
    metadata = {
        "max_completion_tokens": 16_384,
        "context_window": 131_072,
    }

    budget = resolve_judge_budget(
        metadata,
        {
            "max_tokens": 1_200,
            "maximum_retry_tokens": 2_048,
        },
    )

    assert budget.configured_initial_tokens == 1_200
    assert budget.configured_retry_tokens == 2_048
    assert budget.effective_initial_tokens == 1_200
    assert budget.effective_retry_tokens == 2_048
    assert budget.model_output_limit == 16_384
    assert budget.platform_output_cap == 4_096


def test_model_and_platform_limits_cap_judge_budget() -> None:
    budget = resolve_judge_budget(
        {"max_output_tokens": 1_536, "context_window": 8_192},
        {
            "max_tokens": 3_000,
            "maximum_retry_tokens": 8_192,
            "platform_output_cap": 32_768,
            "maximum_input_tokens": 8_000,
        },
    )

    assert budget.effective_initial_tokens == 1_536
    assert budget.effective_retry_tokens == 1_536
    assert budget.platform_output_cap == 4_096
    assert budget.maximum_input_tokens == 6_156


def test_normalized_config_uses_fixed_budget_and_provider_default_reasoning() -> None:
    config = normalized_judge_config(
        {"max_completion_tokens": 32_768},
        {
            "max_tokens": 800,
            "maximum_retry_tokens": 8_192,
            "attempts": 10,
        },
    )

    assert config["output_budget_policy"] == "fixed"
    assert config["max_tokens"] == 800
    assert config["maximum_retry_tokens"] == 4_096
    assert config["attempts"] == 4
    assert config["reasoning_policy"] == "provider_default"


def test_reasoning_support_is_not_inferred_from_model_name() -> None:
    assert explicit_reasoning_support({"model": "deepseek/deepseek-r1"}) is False
    assert explicit_reasoning_support({"supports_reasoning": True}) is True
    assert explicit_reasoning_support({"capabilities": {"reasoning": {}}}) is True


def test_response_strategy_uses_model_capabilities_and_provider_fallback() -> None:
    assert judge_response_strategy(
        "openrouter",
        {"supported_parameters": ["response_format"]},
    ) == "json_object"
    assert judge_response_strategy(
        "custom",
        {"supported_parameters": ["structured_outputs"]},
    ) == "json_schema"
    assert judge_response_strategy("openrouter", {}) == "json_object"
    assert judge_response_strategy("custom", {}) == "text"
