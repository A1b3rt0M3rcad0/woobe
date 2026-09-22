from __future__ import annotations

from copy import deepcopy

from modules.agent.application.context_manager_sdk import (
    ContextCheckpointBoundary,
    ContextManagerState,
)
from modules.agent.infra.context_management.manager_runtime.state import (
    RuntimeContextManagerStateStore,
)


class RuntimeContextCheckpoint:
    """Persist Context Manager state without exposing journal plumbing."""

    __slots__ = ("_manager_name", "_runtime_context", "_state_store")

    def __init__(
        self,
        *,
        manager_name: str,
        runtime_context,
        state_store: RuntimeContextManagerStateStore,
    ) -> None:
        self._manager_name = manager_name
        self._runtime_context = runtime_context
        self._state_store = state_store

    async def save(
        self,
        state: ContextManagerState,
        boundary: ContextCheckpointBoundary,
    ) -> None:
        payload = {
            "manager_name": self._manager_name,
            "boundary": boundary.value,
            "state": self._state_store.dump(state),
        }

        recorder = getattr(self._runtime_context, "run_event_recorder", None)
        if recorder is not None:
            await recorder.emit(
                "context.checkpoint",
                payload,
                durable=True,
            )

        # Publish hot state only after durable persistence succeeds. When no durable
        # recorder exists (unit/local contexts), the state remains Run-local only.
        try:
            setattr(
                self._runtime_context,
                "context_manager_state",
                deepcopy(payload),
            )
        except (AttributeError, TypeError):
            pass
