from __future__ import annotations

from modules.evaluation.application.token_budget import (
    budget_sections,
    estimate_tokens,
    recommended_generation_output_tokens,
)


def test_budget_preserves_required_sections() -> None:
    result = budget_sections(
        [
            ("test_case", {"message": "hello", "expected": "world"}, 10, True),
            ("target_output", {"answer": "ok"}, 10, True),
            ("tool_outputs", [{"payload": "x" * 50_000}], 1, False),
        ],
        maximum_input_tokens=2_000,
        reserved_output_tokens=500,
        safety_margin_tokens=500,
        context_window=8_000,
    )

    assert "test_case" in result.payload
    assert "target_output" in result.payload
    assert result.report.maximum_input_tokens == 1_500
    assert result.report.safety_margin_tokens == 500
    assert result.report.estimated_input_tokens <= result.report.maximum_input_tokens
    assert result.report.truncation_applied is True


def test_context_window_can_reduce_configured_payload_budget() -> None:
    result = budget_sections(
        [("required", "x" * 100_000, 10, True)],
        maximum_input_tokens=16_000,
        reserved_output_tokens=3_000,
        safety_margin_tokens=1_000,
        context_window=8_000,
    )

    assert result.report.maximum_input_tokens == 4_000
    assert result.report.estimated_input_tokens <= 4_000


def test_generation_output_reserve_scales_with_case_count() -> None:
    assert recommended_generation_output_tokens(20) > recommended_generation_output_tokens(5)
    assert recommended_generation_output_tokens(100) <= 12_000


def test_ten_case_generation_reserves_reasoning_and_json_headroom() -> None:
    assert recommended_generation_output_tokens(10) >= 8_000


def test_token_estimate_is_conservative_and_nonzero() -> None:
    assert estimate_tokens("") >= 1
    assert estimate_tokens("a" * 3_200) >= 1_000
