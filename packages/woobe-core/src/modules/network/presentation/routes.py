from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Request

from modules.network.infra.database.models import NetworkExecutionModel
from modules.network.presentation.reattach_routes import (
    _durable_state as _network_durable_state,
    network_runtime_sse,
)
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.infra.errors import NotFoundError
from shared.runtime_reattach import RuntimeStreamFrame, RuntimeStreamGapError, RuntimeStreamReader


router = APIRouter(prefix="/network", tags=["network"])
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


async def _execution_stream(
    request: Request,
    execution_id: UUID,
    project_id: UUID,
    start_sequence: int,
) -> AsyncIterator[str]:
    # Compatibility helper used by ChatSurface until that bounded context migrates.
    del start_sequence
    async with request.app.state.session_factory() as session:
        initial = await session.get(NetworkExecutionModel, execution_id)
    if initial is None or initial.project_id != project_id:
        raise NotFoundError("Network execution not found")

    reader = RuntimeStreamReader(
        EXECUTION_STATE_STORE,
        heartbeat_seconds=request.app.state.settings.network_stream_heartbeat_seconds,
        block_ms=500,
    )

    async def durable_fallback() -> dict | None:
        async with request.app.state.session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
        if execution is None or execution.project_id != project_id:
            raise NotFoundError("Network execution not found")
        return _network_durable_state(execution)

    hot = await EXECUTION_STATE_STORE.get(execution_id)
    if hot is None and str(initial.status) not in TERMINAL_STATUSES:
        queued = _network_durable_state(initial)
        queued.update(
            {
                "run_id": str(execution_id),
                "kind": "NETWORK",
                "sequence": 0,
                "realtime_available": False,
            }
        )
        yield network_runtime_sse(
            RuntimeStreamFrame("run.state", queued, sequence=0),
            execution_id,
        )
        while hot is None:
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.25)
            async with request.app.state.session_factory() as session:
                latest = await session.get(NetworkExecutionModel, execution_id)
            if latest is None or latest.project_id != project_id:
                raise NotFoundError("Network execution not found")
            if str(latest.status) in TERMINAL_STATUSES:
                terminal = _network_durable_state(latest)
                terminal.update(
                    {
                        "run_id": str(execution_id),
                        "kind": "NETWORK",
                        "sequence": 0,
                        "realtime_available": False,
                    }
                )
                yield network_runtime_sse(
                    RuntimeStreamFrame("run.state", terminal, sequence=0),
                    execution_id,
                )
                return
            hot = await EXECUTION_STATE_STORE.get(execution_id)

    try:
        async for frame in reader.stream(
            execution_id,
            "network",
            durable_fallback=durable_fallback,
        ):
            if await request.is_disconnected():
                return
            yield network_runtime_sse(frame, execution_id)
    except RuntimeStreamGapError:
        durable = await durable_fallback()
        if durable is None:
            raise
        degraded = {
            **durable,
            "run_id": str(execution_id),
            "kind": "NETWORK",
            "sequence": 0,
            "realtime_available": False,
            "degraded_reason": "runtime_event_gap",
        }
        yield network_runtime_sse(
            RuntimeStreamFrame("run.state", degraded, sequence=0),
            execution_id,
        )
