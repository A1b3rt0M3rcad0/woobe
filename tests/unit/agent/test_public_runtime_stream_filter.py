import json

from woobe_api.http.agent.controllers.ask_agent_stream_controller import (
    _is_public_stream_chunk,
)


_RUN_ID = "11111111-1111-4111-8111-111111111111"
_SESSION_ID = "22222222-2222-4222-8222-222222222222"


def _event(event_type: str, payload: dict, *, sequence: int = 1) -> str:
    envelope = {
        "protocol_version": 2,
        "event_id": f"33333333-3333-4333-8333-{sequence:012d}",
        "run_id": _RUN_ID,
        "session_id": _SESSION_ID,
        "run_kind": "AGENT",
        "sequence": sequence,
        "type": event_type,
        "occurred_at": "2026-09-17T00:00:00+00:00",
        "payload": payload,
    }
    return (
        f"id: {sequence}\n"
        f"event: {event_type}\n"
        f"data: {json.dumps(envelope)}\n\n"
    )


def test_public_agent_stream_rejects_legacy_tool_planning_tokens() -> None:
    assert _is_public_stream_chunk(
        _event(
            "token",
            {
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
                "visibility": "assistant",
                "channel": "final",
                "phase": "final_response_generation",
                "content": "public recovery answer",
            },
        )
    ) is True


def test_public_agent_stream_accepts_strategy_final_tokens_by_output_mode() -> None:
    assert _is_public_stream_chunk(
        _event(
            "token",
            {
                "visibility": "assistant",
                "channel": "final",
                "phase": "conclusion",
                "output_mode": "final",
                "content": "scientific conclusion streamed progressively",
            },
        )
    ) is True


def test_public_agent_stream_rejects_explicit_internal_token_even_on_legacy_public_phase() -> None:
    assert _is_public_stream_chunk(
        _event(
            "token",
            {
                "visibility": "assistant",
                "channel": "final",
                "phase": "response_generation",
                "output_mode": "internal",
                "content": "must remain internal",
            },
        )
    ) is False


def test_public_agent_stream_preserves_intermediate_assistant_events() -> None:
    assert _is_public_stream_chunk(
        _event(
            "assistant_message_delta",
            {
                "message_id": "message-progress",
                "content": "Vou ",
                "phase": "search",
                "output_mode": "intermediate",
            },
        )
    ) is True
    assert _is_public_stream_chunk(
        _event(
            "assistant_message_completed",
            {
                "message_id": "message-progress",
                "content": "Vou procurar.",
                "phase": "search",
                "output_mode": "intermediate",
                "partial": False,
            },
        )
    ) is True


def test_public_agent_stream_preserves_token_retract_for_promotion() -> None:
    assert _is_public_stream_chunk(
        _event(
            "token_retract",
            {
                "message_id": "message-final",
                "content_length": 12,
                "reason": "tool_call_selected",
            },
        )
    ) is True


def test_public_agent_stream_preserves_non_token_events() -> None:
    assert _is_public_stream_chunk(
        _event("done", {"answer": "public answer"})
    ) is True
