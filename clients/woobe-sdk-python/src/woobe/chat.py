from __future__ import annotations

import asyncio
from contextlib import aclosing
from typing import Any, Literal
from uuid import uuid4

from woobe._transport.http import RuntimeTransport
from woobe._transport.sse import RuntimeControlFrame, parse_runtime_frame
from woobe.errors import (
    WoobeConnectionError,
    WoobeProtocolError,
    WoobeRecoveryError,
    WoobeRequestError,
    WoobeStreamGapError,
)
from woobe.events import WoobeEvent
from woobe.results import ChatResult

TargetKind = Literal["AGENT", "NETWORK"]
_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}
_TERMINAL_EVENT_TYPES = {
    "done",
    "error",
    "cancelled",
    "execution_completed",
    "execution_failed",
    "execution_cancelled",
    "execution_timed_out",
}


class Chat:
    """Lazy runtime interaction.

    Constructing a Chat performs no HTTP request. The initial Runtime request starts
    only when ``events()`` is iterated.
    """

    def __init__(
        self,
        *,
        transport: RuntimeTransport,
        target_kind: TargetKind,
        target_alias: str,
        key: str,
        input: str,
        session_id: str | None,
        external_context: dict[str, Any] | None,
        max_reconnect_attempts: int,
        reconnect_base_delay_seconds: float,
    ) -> None:
        self._transport = transport
        self._target_kind = target_kind
        self._target_alias = target_alias
        self._key = key
        self._input = input
        self._session_id = session_id
        self._external_context = (
            dict(external_context) if external_context is not None else None
        )
        self._run_id: str | None = None
        self._result: ChatResult | None = None
        self._last_sequence: int | None = None
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_base_delay_seconds = reconnect_base_delay_seconds
        self._idempotency_key = str(uuid4())
        self._started = False

    @property
    def target_alias(self) -> str:
        return self._target_alias

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def run_id(self) -> str | None:
        return self._run_id

    @property
    def result(self) -> ChatResult | None:
        return self._result

    async def events(self):
        """Execute lazily and yield canonical semantic ``WoobeEvent`` objects.

        Transport/control frames remain internal to the SDK. After a canonical Run ID
        is known, recovery always uses the reattach GET for that same Run.
        """

        if self._started:
            raise WoobeProtocolError("Chat.events() can only be consumed once")
        self._started = True

        mode: Literal["new", "reattach"] = "new"
        reconnect_attempt = 0

        while True:
            try:
                source = (
                    self._transport.stream_new_run(
                        key=self._key,
                        message=self._input,
                        session_id=self._session_id,
                        external_context=self._external_context,
                        idempotency_key=self._idempotency_key,
                    )
                    if mode == "new"
                    else self._transport.stream_run(key=self._key, run_id=self._require_run_id())
                )

                async with aclosing(source):
                    async for frame in source:
                        parsed = parse_runtime_frame(frame)
                        if isinstance(parsed, RuntimeControlFrame):
                            self._handle_control_frame(parsed)
                            continue

                        self._accept_identity(parsed)
                        if not self._accept_sequence(parsed):
                            continue

                        terminal = self._is_terminal(parsed)
                        if self._has_result(parsed):
                            self._result = ChatResult.from_event(parsed)

                        yield parsed
                        if terminal:
                            return

                raise WoobeConnectionError("Runtime stream ended before terminal state")

            except (WoobeConnectionError, WoobeStreamGapError) as exc:
                mode, reconnect_attempt = await self._recover(
                    mode=mode,
                    reconnect_attempt=reconnect_attempt,
                    cause=exc,
                )
            except WoobeRequestError as exc:
                if not exc.retryable:
                    raise
                mode, reconnect_attempt = await self._recover(
                    mode=mode,
                    reconnect_attempt=reconnect_attempt,
                    cause=exc,
                )

    def _accept_identity(self, event: WoobeEvent) -> None:
        if event.run_kind != self._target_kind:
            raise WoobeProtocolError(
                f"Runtime returned run_kind={event.run_kind} for {self._target_kind} target"
            )
        if self._run_id is not None and self._run_id != event.run_id:
            raise WoobeProtocolError(
                f"Runtime stream changed Run identity from {self._run_id} to {event.run_id}"
            )
        if self._session_id is not None and self._session_id != event.session_id:
            raise WoobeProtocolError(
                "Runtime stream returned a Session different from the requested Session"
            )
        self._run_id = event.run_id
        self._session_id = event.session_id

    @staticmethod
    def _handle_control_frame(frame: RuntimeControlFrame) -> None:
        if frame.type != "error":
            return
        message = frame.payload.get("message") or frame.payload.get("detail")
        if not isinstance(message, str) or not message.strip():
            message = "Woobe Runtime rejected the request before Run acceptance"
        status_code = frame.payload.get("status_code")
        if isinstance(status_code, bool) or not isinstance(status_code, int):
            status_code = None
        raise WoobeRequestError(message, status_code=status_code)

    async def _recover(
        self,
        *,
        mode: Literal["new", "reattach"],
        reconnect_attempt: int,
        cause: Exception,
    ) -> tuple[Literal["new", "reattach"], int]:
        if self._run_id is None and self._session_id is not None:
            self._run_id = await self._transport.resolve_active_run(
                key=self._key,
                session_id=self._session_id,
            )

        if self._run_id is None:
            if self._target_kind == "NETWORK" and mode == "new":
                if reconnect_attempt >= self._max_reconnect_attempts:
                    raise WoobeRecoveryError(
                        "Network Run could not be recovered before its canonical ID was observed"
                    ) from cause
                await self._wait(reconnect_attempt)
                return "new", reconnect_attempt + 1

            raise WoobeRecoveryError(
                "Runtime connection failed before the canonical Run could be recovered; "
                "the SDK will not submit another Agent execution because "
                "that could duplicate the Run"
            ) from cause

        if reconnect_attempt >= self._max_reconnect_attempts:
            raise WoobeRecoveryError(
                f"Run {self._run_id} exceeded the reattach retry budget"
            ) from cause

        await self._wait(reconnect_attempt)
        return "reattach", reconnect_attempt + 1

    async def _wait(self, reconnect_attempt: int) -> None:
        delay = self._reconnect_base_delay_seconds * (reconnect_attempt + 1)
        if delay > 0:
            await asyncio.sleep(delay)

    def _accept_sequence(self, event: WoobeEvent) -> bool:
        sequence = event.sequence

        if event.type == "run.state":
            if event.payload.get("realtime_available") is False:
                return True
            if self._last_sequence is not None and sequence < self._last_sequence:
                return False
            self._last_sequence = sequence
            return True

        if self._last_sequence is not None:
            if sequence <= self._last_sequence:
                return False
            expected = self._last_sequence + 1
            if sequence != expected:
                raise WoobeStreamGapError(
                    f"Runtime event sequence gap: expected {expected}, received {sequence}"
                )
        self._last_sequence = sequence
        return True

    @staticmethod
    def _is_terminal(event: WoobeEvent) -> bool:
        if event.type in _TERMINAL_EVENT_TYPES:
            return True
        if event.type != "run.state":
            return False
        status = event.payload.get("status")
        return isinstance(status, str) and status.lower() in _TERMINAL_STATUSES

    @staticmethod
    def _has_result(event: WoobeEvent) -> bool:
        if event.type in {"done", "execution_completed"}:
            return True
        if event.type != "run.state":
            return False
        status = event.payload.get("status")
        return isinstance(status, str) and status.lower() == "completed"

    def _require_run_id(self) -> str:
        if self._run_id is None:
            raise WoobeProtocolError("Canonical Run ID is not available")
        return self._run_id
