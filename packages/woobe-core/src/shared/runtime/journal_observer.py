from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from shared.contracts.run_event_journal import RunEventJournalPort
from shared.runtime.contracts import RunReference, RuntimeFrame
from shared.runtime.journal_projection import journal_runtime_state
from shared.runtime.observer import DurableFallback
from shared.runtime.observer import RuntimeObserver as BaseRuntimeObserver


_DEFAULT_RUNTIME_JOURNAL: RunEventJournalPort | None = None


def configure_runtime_journal(journal: RunEventJournalPort | None) -> None:
    """Configure the process-wide durable observer source at the composition root."""

    global _DEFAULT_RUNTIME_JOURNAL
    _DEFAULT_RUNTIME_JOURNAL = journal


class JournalAwareRuntimeObserver(BaseRuntimeObserver):
    """Runtime observer that falls back to the durable Mongo journal before SQL alone.

    Redis remains the realtime source. When hot state is absent or unavailable, the
    caller's relational fallback supplies authorization/read-model metadata and the
    journal rebuilds the public projection through its contiguous durable watermark.
    """

    def __init__(
        self,
        *args: Any,
        journal: RunEventJournalPort | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._journal = journal if journal is not None else _DEFAULT_RUNTIME_JOURNAL

    def _journal_fallback(
        self,
        run: RunReference,
        durable_fallback: DurableFallback,
    ) -> DurableFallback:
        if self._journal is None or getattr(
            durable_fallback,
            "_woobe_journal_aware",
            False,
        ):
            return durable_fallback

        async def resolved() -> dict[str, Any] | None:
            base = await durable_fallback()
            if isinstance(base, dict) and base.get("durable_source") == "mongodb_journal":
                return base
            return await journal_runtime_state(
                self._journal,
                run.run_id,
                run.kind.value,
                base_state=base,
            )

        setattr(resolved, "_woobe_journal_aware", True)
        return resolved

    @staticmethod
    def _restore_journal_sequence(
        state: dict[str, Any],
        cursor: str | None,
    ) -> None:
        durable_sequence = state.get("journal_durable_sequence")
        if (
            cursor is None
            and state.get("durable_source") == "mongodb_journal"
            and isinstance(durable_sequence, int)
            and not isinstance(durable_sequence, bool)
        ):
            state["sequence"] = durable_sequence

    async def current_state(
        self,
        run: RunReference,
        *,
        durable_fallback: DurableFallback,
    ) -> tuple[dict[str, Any], str | None]:
        state, cursor = await super().current_state(
            run,
            durable_fallback=self._journal_fallback(run, durable_fallback),
        )
        self._restore_journal_sequence(state, cursor)
        return state, cursor

    async def observe(
        self,
        run: RunReference,
        *,
        durable_fallback: DurableFallback,
        disconnect_check=None,
    ) -> AsyncIterator[RuntimeFrame]:
        async for frame in super().observe(
            run,
            durable_fallback=self._journal_fallback(run, durable_fallback),
            disconnect_check=disconnect_check,
        ):
            if frame.event_type == "run.state" and frame.sequence is None:
                data = dict(frame.data)
                self._restore_journal_sequence(data, None)
                durable_sequence = data.get("sequence")
                if (
                    isinstance(durable_sequence, int)
                    and not isinstance(durable_sequence, bool)
                ):
                    frame = RuntimeFrame(
                        frame.event_type,
                        data,
                        sequence=durable_sequence,
                    )
            yield frame


__all__ = ["JournalAwareRuntimeObserver", "configure_runtime_journal"]
