from __future__ import annotations

from modules.evaluation.infra.governed_judge import (
    affordable_output_tokens,
    is_terminal_judge_error,
)


def test_openrouter_credit_error_is_terminal_and_exposes_affordable_tokens() -> None:
    error = (
        "APIStatusError: Error code: 402 - This request requires more credits, "
        "or fewer max_tokens. You requested up to 16384 tokens, but can only afford 1437."
    )

    assert is_terminal_judge_error(error) is True
    assert affordable_output_tokens(error) == 1437


def test_parse_or_output_errors_are_not_terminal() -> None:
    assert is_terminal_judge_error("JSONDecodeError: invalid JSON") is False
    assert is_terminal_judge_error("LengthFinishReasonError: length limit was reached") is False
    assert affordable_output_tokens("JSONDecodeError") is None


def test_credentials_and_model_availability_open_terminal_policy() -> None:
    assert is_terminal_judge_error("APIStatusError: Error code: 401 unauthorized") is True
    assert is_terminal_judge_error("No endpoints found for this model") is True
