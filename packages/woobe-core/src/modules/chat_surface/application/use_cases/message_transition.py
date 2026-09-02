from modules.chat_surface.application.dtos.message_request import (
    CanonicalRunState,
    MarkMessageRequestInput,
    MessageRequestState,
    MessageTransitionDecision,
)


_AGENT_TERMINAL = {"completed", "failed", "cancelled", "uncertain"}
_NETWORK_TERMINAL = {"completed", "failed", "cancelled", "timed_out", "uncertain"}
_MESSAGE_ACTIVE = {"accepted", "streaming"}


def terminal_statuses(target_type: str) -> set[str]:
    return _AGENT_TERMINAL if target_type == "agent" else _NETWORK_TERMINAL


def resolve_message_transition(
    *,
    target_type: str,
    current: MessageRequestState,
    requested: MarkMessageRequestInput,
    canonical_run: CanonicalRunState | None,
) -> MessageTransitionDecision:
    requested_terminal = requested.status in {"completed", "failed", "cancelled"}
    canonical_terminal = terminal_statuses(target_type)

    if requested_terminal and canonical_run is not None:
        if canonical_run.status not in canonical_terminal:
            return MessageTransitionDecision(
                status="streaming",
                target_run_id=canonical_run.id,
                error_code=None,
            )
        final_status = (
            "completed"
            if canonical_run.status == "completed"
            else "cancelled"
            if canonical_run.status == "cancelled"
            else "failed"
        )
        return MessageTransitionDecision(
            status=final_status,
            target_run_id=canonical_run.id,
            error_code=(
                None
                if final_status in {"completed", "cancelled"}
                else requested.error_code or "runtime_failed"
            ),
        )

    if (
        requested.status == "completed"
        and canonical_run is None
        and current.status in _MESSAGE_ACTIVE
    ):
        return MessageTransitionDecision(
            status="streaming",
            target_run_id=requested.target_run_id or current.target_run_id,
            error_code=None,
        )

    return MessageTransitionDecision(
        status=requested.status,
        target_run_id=(
            canonical_run.id
            if canonical_run is not None
            else requested.target_run_id or current.target_run_id
        ),
        error_code=requested.error_code,
    )
