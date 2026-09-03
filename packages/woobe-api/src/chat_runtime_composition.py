from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from modules.agent.entrypoint import AskInput, build_agent_stream_service, commit_safe_stream
from modules.chat_surface.application.runtime_gateway import (
    ChatRuntimeChunk,
    ChatRuntimeRequest,
    DisconnectCheck,
    PreparedChatRuntime,
)
from modules.network.application.service import NetworkApplicationService
from modules.network.infra.database.models import NetworkExecutionModel
from modules.network.presentation.routes import _execution_stream
from shared.infra.errors import ConflictError, NotFoundError

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
    """Outer composition that lets ChatSurface consume canonical Agent/Network runtime.

    ChatSurface owns session/admission semantics. Target-specific execution wiring stays
    in the API composition root so the ChatSurface bounded context does not implement a
    second Agent or Network runtime.
    """

    def __init__(self, *, session_factory, settings, app_state) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._app_state = app_state

    def _network_service(self) -> NetworkApplicationService:
        return NetworkApplicationService(
            self._session_factory,
            hard_max_depth=self._settings.network_max_depth_hard,
            hard_max_invocations=self._settings.network_max_invocations_hard,
            hard_timeout_seconds=self._settings.network_timeout_hard_seconds,
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
        execution: NetworkExecutionModel,
        project_id: UUID,
        disconnect_check: DisconnectCheck,
    ) -> AsyncIterator[ChatRuntimeChunk]:
        request_adapter = _NetworkRequestAdapter(
            state=self._app_state,
            disconnect_check=disconnect_check,
        )
        async for chunk in _execution_stream(
            request_adapter,
            execution.id,
            project_id,
            0,
        ):
            run_id, terminal_status = _runtime_metadata(chunk)
            yield ChatRuntimeChunk(
                sse=chunk,
                run_id=run_id or execution.id,
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
        elif runtime_request.existing_run_id is not None:
            async with self._session_factory() as session:
                execution = await session.get(
                    NetworkExecutionModel,
                    runtime_request.existing_run_id,
                )
            if (
                execution is None
                or execution.project_id != runtime_request.project_id
                or execution.network_id != runtime_request.target_id
                or execution.network_version_id != runtime_request.target_release_id
                or execution.network_session_id != runtime_request.session_id
            ):
                raise NotFoundError("Network execution not found")
        else:
            raise ConflictError(
                "Network message request is accepted but its execution is not ready"
            )

        return PreparedChatRuntime(
            run_id=execution.id,
            headers={
                "X-Network-Execution-ID": str(execution.id),
                "X-Woobe-Run-ID": str(execution.id),
            },
            stream=self._network_stream(
                execution=execution,
                project_id=runtime_request.project_id,
                disconnect_check=disconnect_check,
            ),
        )
