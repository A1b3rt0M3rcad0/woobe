from modules.agent.composition.runtime.runtime_output_validation import (
    EmptyModelOutputError,
)
from modules.network.infra.runtime.agent_invoker import (
    _caused_by_empty_model_output,
    _is_public_runtime_token,
)
from modules.network.presentation.public_runtime import _public_failure_message


def _wrapped_empty_output_error() -> Exception:
    try:
        raise EmptyModelOutputError(
            "Model completed without producing public output"
        )
    except EmptyModelOutputError:
        try:
            raise ValueError(
                "AI provider error: Model completed without producing public output"
            )
        except ValueError as wrapped:
            return wrapped


def test_empty_output_is_detected_through_exception_context() -> None:
    assert _caused_by_empty_model_output(_wrapped_empty_output_error()) is True


def test_unrelated_error_is_not_classified_as_empty_output() -> None:
    assert _caused_by_empty_model_output(ValueError("provider timeout")) is False


def test_public_network_failure_message_is_explicit() -> None:
    assert _public_failure_message("empty_model_output") == (
        "The Agent completed without producing a public result."
    )


def test_network_stream_rejects_tool_planning_tokens() -> None:
    assert _is_public_runtime_token(
        {
            "visibility": "assistant",
            "channel": "final",
            "phase": "tool_planning",
        }
    ) is False


def test_network_stream_accepts_final_response_tokens() -> None:
    assert _is_public_runtime_token(
        {
            "visibility": "assistant",
            "channel": "final",
            "phase": "final_response_generation",
        }
    ) is True
