from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from modules.agent.entrypoint import (
    AskInput,
    build_agent_run_reattach_operations,
    build_agent_stream_service,
)
from modules.chat_surface.entrypoint import (
    ChatRunIdentity,
    ChatRuntimeChunk,
    ChatRuntimeRequest,
    ChatRuntimeTarget,
    DisconnectCheck,
    PreparedChatRuntime,
)
from modules.network.entrypoint import NetworkBoundaryService, build_network_service
from woobe_api.http.network.reattach_routes import (
    network_runtime_sse,
)
from woobe_api.http.network.runtime_routes import _execution_stream
from woobe_api.http.agent.controllers.ask_agent_stream_controller import (
    commit_safe_stream,
)
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.infra.errors import ConflictError, NotFoundError
from shared.runtime import (
    RunReference,
    RuntimeFrame,
    RuntimeObserver,
    RuntimeStreamGapError,
    format_sse_frame,
)

_TERMINAL_BY_EVENT = {
    "done": "completed",
    "execution_completed": "completed",
    "cancelled": "cancelled",
    "execution_cancelled": "cancelled",
    "error": "failed",
    "execution_failed": "failed",
}
_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


class _DisconnectAdapter:
    def __init__(self, disconnect_check: DisconnectCheck) -> None:
        self._disconnect_check = disconnect_check

    async def is_disconnected(self) -> bool:
        return await self._disconnect_check()


class _NetworkRequestAdapter(_DisconnectAdapter):
    def __init__(self, *, state, disconnect_check: DisconnectCheck) -> None:
        super().__init__(disconnect_check)
        self.app = SimpleNamespace(state=state)


def _parse_sse(chunk: str) -> tuple[str | None, dict]:
    event_type: str | None = None
    payload: dict = {}
    for line in chunk.splitlines():
        if line.startswith("event:"):
            candidate = line.removeprefix("event:").strip()
            event_type = candidate or None
        elif line.startswith("data:"):
            try:
                decoded = json.loads(line.removeprefix("data:").strip())
            except (json.JSONDecodeError, TypeError):
                decoded = None
            if isinstance(decoded, dict):
                payload = decoded
    if event_type is None:
        candidate = payload.get("type")
        if isinstance(candidate, str):
            event_type = candidate
    return event_type, payload


def _runtime_metadata(chunk: str) -> tuple[UUID | None, str | None]:
    event_type, payload = _parse_sse(chunk)
    nested = payload.get("data")
    state = nested if isinstance(nested, dict) else payload

    raw_run_id = payload.get("run_id") or payload.get("execution_id") or state.get("run_id")
    run_id: UUID | None = None
    if raw_run_id:
        try:
            run_id = UUID(str(raw_run_id))
        except (TypeError, ValueError):
            run_id = None

    terminal_status = _TERMINAL_BY_EVENT.get(str(event_type or ""))
    raw_status = state.get("status")
    if isinstance(raw_status, str) and raw_status in _TERMINAL_STATUSES:
        terminal_status = raw_status
    return run_id, terminal_status


class ApiChatRuntimeGateway:
    """Outer composition for every ChatSurface interaction with Agent/Network runtime.

    ChatSurface owns session, admission and message bookkeeping. Target-specific Run
    discovery, execution, observation and cancellation stay in the API composition root.
    """

    def __init__(self, *, settings, app_state) -> None:
        self._app_state = app_state
        self._agent_runs = build_agent_run_reattach_operations()
        self._observer = RuntimeObserver(
            EXECUTION_STATE_STORE,
            heartbeat_seconds=settings.network_stream_heartbeat_seconds,
            block_ms=500,
        )

    def _network_service(self) -> NetworkBoundaryService:
        return build_network_service()

    async def resolve_run(
        self,
        target: ChatRuntimeTarget,
        *,
        preferred_run_id: UUID | None = None,
        created_after: datetime | None = None,
    ) -> ChatRunIdentity | None:
        if target.target_type == "agent":
            run = await self._agent_runs.resolve_target_run(
                project_id=target.project_id,
                agent_id=target.target_id,
                session_id=target.session_id,
                agent_release_id=target.target_release_id,
                preferred_run_id=preferred_run_id,
                created_after=created_after,
            )
            if run is None:
                return None
            return ChatRunIdentity(run["run_id"], run["status"])

        if target.target_type != "network":
            raise ConflictError("Unsupported ChatSurface runtime target")

        execution = await self._network_service().resolve_chat_surface_run(
            project_id=target.project_id,
            network_id=target.target_id,
            network_session_id=target.session_id,
            network_version_id=target.target_release_id,
            preferred_run_id=preferred_run_id,
            created_after=created_after,
        )
        if execution is None:
            return None
        return ChatRunIdentity(
            UUID(str(execution["run_id"])),
            str(execution["status"]),
        )

    async def _agent_stream(
        self,
        runtime_request: ChatRuntimeRequest,
        disconnect_check: DisconnectCheck,
    ) -> AsyncIterator[ChatRuntimeChunk]:
        input_dto = AskInput(
            project_id=runtime_request.project_id,
            agent_id=runtime_request.target_id,
            message=runtime_request.message,
            session_id=runtime_request.session_id,
            tenant_id=str(runtime_request.surface_id),
            metadata={
                **runtime_request.metadata,
                "source": (
                    "chat_surface_test"
                    if runtime_request.session_source == "control_plane_test"
                    else "chat_surface"
                ),
                "chat_surface_session_source": runtime_request.session_source,
                "chat_surface_id": str(runtime_request.surface_id),
                "chat_surface_target_release_id": str(runtime_request.target_release_id),
                "embed_protocol_version": 1,
                "server_received_at": datetime.now(timezone.utc).isoformat(),
            },
            execution_context="production",
            loaded_release_id=runtime_request.target_release_id,
        )
        service = build_agent_stream_service()
        adapter = _DisconnectAdapter(disconnect_check)
        async for chunk in commit_safe_stream(service, input_dto, adapter):
            run_id, terminal_status = _runtime_metadata(chunk)
            yield ChatRuntimeChunk(
                sse=chunk,
                run_id=run_id,
                terminal_status=terminal_status,
            )

    async def _network_stream(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
        disconnect_check: DisconnectCheck,
    ) -> AsyncIterator[ChatRuntimeChunk]:
        request_adapter = _NetworkRequestAdapter(
            state=self._app_state,
            disconnect_check=disconnect_check,
        )
        async for chunk in _execution_stream(
            request_adapter,
            execution_id,
            project_id,
            0,
        ):
            run_id, terminal_status = _runtime_metadata(chunk)
            yield ChatRuntimeChunk(
                sse=chunk,
                run_id=run_id or execution_id,
                terminal_status=terminal_status,
            )

    async def prepare(
        self,
        runtime_request: ChatRuntimeRequest,
        disconnect_check: DisconnectCheck,
    ) -> PreparedChatRuntime:
        if runtime_request.target_type == "agent":
            if not runtime_request.created:
                raise ConflictError(
                    "Agent message request already exists; reload Session history"
                )
            return PreparedChatRuntime(
                stream=self._agent_stream(runtime_request, disconnect_check),
            )

        if runtime_request.target_type != "network":
            raise ConflictError("Unsupported ChatSurface runtime target")

        if runtime_request.created:
            execution = await self._network_service().submit_execution(
                network_id=runtime_request.target_id,
                project_id=runtime_request.project_id,
                network_session_id=runtime_request.session_id,
                message=runtime_request.message,
                idempotency_key=f"chat:{runtime_request.message_request_id}",
            )
            execution_id = execution.id
        elif runtime_request.existing_run_id is not None:
            existing = await self._network_service().resolve_chat_surface_run(
                project_id=runtime_request.project_id,
                network_id=runtime_request.target_id,
                network_session_id=runtime_request.session_id,
                network_version_id=runtime_request.target_release_id,
                preferred_run_id=runtime_request.existing_run_id,
            )
            if existing is None:
                raise NotFoundError("Network execution not found")
            execution_id = UUID(str(existing["run_id"]))
        else:
            raise ConflictError(
                "Network message request is accepted but its execution is not ready"
            )

        return PreparedChatRuntime(
            run_id=execution_id,
            headers={
                "X-Network-Execution-ID": str(execution_id),
                "X-Woobe-Run-ID": str(execution_id),
            },
            stream=self._network_stream(
                execution_id=execution_id,
                project_id=runtime_request.project_id,
                disconnect_check=disconnect_check,
            ),
        )

    async def observe(
        self,
        target: ChatRuntimeTarget,
        run_id: UUID,
        disconnect_check: DisconnectCheck,
    ) -> PreparedChatRuntime:
        if target.target_type == "agent":
            await self._agent_runs.durable_target_state(
                run_id=run_id,
                project_id=target.project_id,
                agent_id=target.target_id,
                session_id=target.session_id,
                agent_release_id=target.target_release_id,
            )
        elif target.target_type == "network":
            await self._network_service().chat_surface_durable_state(
                execution_id=run_id,
                project_id=target.project_id,
                network_id=target.target_id,
                network_session_id=target.session_id,
                network_version_id=target.target_release_id,
            )
        else:
            raise ConflictError("Unsupported ChatSurface runtime target")

        async def stream() -> AsyncIterator[ChatRuntimeChunk]:
            if target.target_type == "agent":
                async def durable_fallback() -> dict | None:
                    return await self._agent_runs.durable_target_state(
                        run_id=run_id,
                        project_id=target.project_id,
                        agent_id=target.target_id,
                        session_id=target.session_id,
                        agent_release_id=target.target_release_id,
                    )

                formatter = format_sse_frame
                run_ref = RunReference.agent(run_id)
                kind = "agent"
            else:
                async def durable_fallback() -> dict | None:
                    return await self._network_service().chat_surface_durable_state(
                        execution_id=run_id,
                        project_id=target.project_id,
                        network_id=target.target_id,
                        network_session_id=target.session_id,
                        network_version_id=target.target_release_id,
                    )

                formatter = lambda frame: network_runtime_sse(frame, run_id)
                run_ref = RunReference.network(run_id)
                kind = "network"

            try:
                async for frame in self._observer.observe(
                    run_ref,
                    durable_fallback=durable_fallback,
                    disconnect_check=disconnect_check,
                ):
                    sse = formatter(frame)
                    _, terminal_status = _runtime_metadata(sse)
                    yield ChatRuntimeChunk(
                        sse=sse,
                        run_id=run_id,
                        terminal_status=terminal_status,
                    )
            except RuntimeStreamGapError:
                durable = await durable_fallback()
                if durable is None:
                    raise
                degraded = {
                    **durable,
                    "run_id": str(run_id),
                    "kind": kind.upper(),
                    "sequence": None,
                    "realtime_available": False,
                    "degraded_reason": "runtime_event_gap",
                }
                sse = formatter(RuntimeFrame("run.state", degraded, sequence=None))
                _, terminal_status = _runtime_metadata(sse)
                yield ChatRuntimeChunk(
                    sse=sse,
                    run_id=run_id,
                    terminal_status=terminal_status,
                )

        headers = {"X-Woobe-Run-ID": str(run_id)}
        if target.target_type == "network":
            headers["X-Network-Execution-ID"] = str(run_id)
        return PreparedChatRuntime(
            stream=stream(),
            run_id=run_id,
            headers=headers,
        )

    async def cancel(
        self,
        target: ChatRuntimeTarget,
        run_id: UUID,
    ) -> ChatRunIdentity:
        if target.target_type == "agent":
            result = await self._agent_runs.cancel_target_run(
                run_id=run_id,
                project_id=target.project_id,
                agent_id=target.target_id,
                session_id=target.session_id,
                agent_release_id=target.target_release_id,
            )
            return ChatRunIdentity(run_id, result["status"])

        if target.target_type != "network":
            raise ConflictError("Unsupported ChatSurface runtime target")

        execution = await self._network_service().resolve_chat_surface_run(
            project_id=target.project_id,
            network_id=target.target_id,
            network_session_id=target.session_id,
            network_version_id=target.target_release_id,
            preferred_run_id=run_id,
        )
        if execution is None:
            raise NotFoundError("Network execution not found")
        status = str(execution["status"])

        if status in _TERMINAL_STATUSES:
            return ChatRunIdentity(run_id, status)
        await self._network_service().request_cancellation(run_id, target.project_id)
        return ChatRunIdentity(run_id, "cancel_requested")
