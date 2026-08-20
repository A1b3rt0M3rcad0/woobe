import json

from modules.agent.presentation.http.controllers.ask_agent_stream_controller import (
    _is_public_stream_chunk,
)


def _event(event_type: str, payload: dict) -> str:
    return (
        f"event: {event_type}\n"
        f"data: {json.dumps(payload)}\n\n"
    )


def test_public_agent_stream_rejects_tool_planning_tokens() -> None:
    assert _is_public_stream_chunk(
        _event(
            "token",
            {
                "type": "token",
                "visibility": "assistant",
                "channel": "final",
                "phase": "tool_planning",
                "content": "internal planning text",
            },
        )
    ) is False


def test_public_agent_stream_accepts_final_response_tokens() -> None:
    assert _is_public_stream_chunk(
        _event(
            "token",
            {
                "type": "token",
                "visibility": "assistant",
                "channel": "final",
                "phase": "final_response_generation",
                "content": "public answer",
            },
        )
    ) is True


def test_public_agent_stream_preserves_non_token_events() -> None:
    assert _is_public_stream_chunk(
        _event("done", {"type": "done", "answer": "public answer"})
    ) is True
