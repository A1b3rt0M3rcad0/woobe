import json

from woobe_api.http.agent.controllers.ask_agent_stream_controller import (
    _is_public_stream_chunk,
)


def _event(event_type: str, payload: dict) -> str:
    return (
        f"event: {event_type}\n"
        f"data: {json.dumps(payload)}\n\n"
    )


def test_public_agent_stream_rejects_legacy_tool_planning_tokens() -> None:
    assert _is_public_stream_chunk(
        _event(
            "token",
            {
                "type": "token",
                "visibility": "assistant",
                "channel": "final",
                "phase": "tool_planning",
                "content": "legacy internal planning text",
            },
        )
    ) is False


def test_public_agent_stream_accepts_committed_capability_response_tokens() -> None:
    assert _is_public_stream_chunk(
        _event(
            "token",
            {
                "type": "token",
                "visibility": "assistant",
                "channel": "final",
                "phase": "capability_response_generation",
                "content": "direct public answer",
            },
        )
    ) is True


def test_public_agent_stream_accepts_terminal_tool_followup_tokens() -> None:
    assert _is_public_stream_chunk(
        _event(
            "token",
            {
                "type": "token",
                "visibility": "assistant",
                "channel": "final",
                "phase": "tool_followup_1",
                "content": "answer after a real capability call",
            },
        )
    ) is True


def test_public_agent_stream_accepts_final_response_tokens() -> None:
    assert _is_public_stream_chunk(
        _event(
            "token",
            {
                "type": "token",
                "visibility": "assistant",
                "channel": "final",
                "phase": "final_response_generation",
                "content": "public recovery answer",
            },
        )
    ) is True


def test_public_agent_stream_preserves_non_token_events() -> None:
    assert _is_public_stream_chunk(
        _event("done", {"type": "done", "answer": "public answer"})
    ) is True

