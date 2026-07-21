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
        context_window=8_000,
    )

    assert "test_case" in result.payload
    assert "target_output" in result.payload
    assert result.report.estimated_input_tokens <= result.report.maximum_input_tokens
    assert result.report.truncation_applied is True


def test_generation_output_reserve_scales_with_case_count() -> None:
    assert recommended_generation_output_tokens(20) > recommended_generation_output_tokens(5)
    assert recommended_generation_output_tokens(100) <= 12_000


def test_token_estimate_is_conservative_and_nonzero() -> None:
    assert estimate_tokens("") >= 1
    assert estimate_tokens("a" * 3_200) >= 1_000
