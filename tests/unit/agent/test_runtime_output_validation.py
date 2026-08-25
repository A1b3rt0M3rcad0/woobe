from types import SimpleNamespace

import pytest

from modules.agent.application.runtime_output_validation import (
    EmptyModelOutputError,
    ensure_model_result_has_public_output,
    ensure_public_output,
    has_public_output,
)


def test_text_output_is_public() -> None:
    assert has_public_output("answer") is True


def test_structured_output_is_public_even_when_text_is_empty() -> None:
    assert has_public_output("", {"status": "ok"}) is True
    ensure_public_output("", {"status": "ok"})


def test_blank_output_is_rejected() -> None:
    with pytest.raises(EmptyModelOutputError):
        ensure_public_output("   ")


def test_internal_only_model_blocks_are_rejected() -> None:
    result = SimpleNamespace(
        content=[
            {
                "type": "reasoning_content",
                "text": "private reasoning",
            }
        ]
    )

    with pytest.raises(EmptyModelOutputError):
        ensure_model_result_has_public_output(result)


def test_public_text_block_is_accepted() -> None:
    result = SimpleNamespace(
        content=[
            {
                "type": "text",
                "text": "public answer",
            }
        ]
    )

    ensure_model_result_has_public_output(result)
