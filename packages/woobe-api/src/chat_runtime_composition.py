from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select

from modules.agent.entrypoint import AskInput, build_agent_stream_service, commit_safe_stream
from modules.agent.infra.database.run_models import AgentRunModel
from modules.chat_surface.application.runtime_gateway import (
    ChatRunIdentity,
    ChatRuntimeChunk,
    ChatRuntimeRequest,
    ChatRuntimeTarget,
    DisconnectCheck,
    PreparedChatRuntime,
)
from modules.network.application.service import NetworkApplicationService
from modules.network.infra.database.models import NetworkExecutionModel
from modules.network.presentation.reattach_routes import (
    _durable_state as network_durable_state,
    network_runtime_sse,
)
from modules.network.presentation.routes import _execution_stream
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
_AGENT_ACTIVE = {"running"}
_NETWORK_ACTIVE = {"queued", "running", "cancel_requested"}


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

    def __init__(self, *, session_factory, settings, app_state) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._app_state = app_state
        self._observer = RuntimeObserver(
            EXECUTION_STATE_STORE,
            heartbeat_seconds=settings.network_stream_heartbeat_seconds,
            block_ms=500,
        )

    def _network_service(self) -> NetworkApplicationService:
        return NetworkApplicationService(
            self._session_factory,
            hard_max_depth=self._settings.network_max_depth_hard,
            hard_max_invocations=self._settings.network_max_invocations_hard,
            hard_timeout_seconds=self._settings.network_timeout_hard_seconds,
        )

    @staticmethod
    def _valid_agent(run: AgentRunModel | None, target: ChatRuntimeTarget) -> bool:
        return bool(
            run is not None
            and run.project_id == target.project_id
            and run.agent_id == target.target_id
            and run.session_id == target.session_id
            and run.agent_release_id == target.target_release_id
            and run.network_execution_id is None
        )

    @staticmethod
    def _valid_network(
        execution: NetworkExecutionModel | None,
        target: ChatRuntimeTarget,
    ) -> bool:
        return bool(
            execution is not None
            and execution.project_id == target.project_id
            and execution.network_id == target.target_id
            and execution.network_session_id == target.session_id
            and execution.network_version_id == target.target_release_id
        )

    @staticmethod
    def _agent_durable_state(run: AgentRunModel) -> dict:
        result = run.result if isinstance(run.result, dict) else None
        answer = result.get("answer") if result else None
        return {
            "status": str(run.status),
            "output": answer or "",
            "result": result,
            "usage": run.usage if isinstance(run.usage, dict) else {},
            "trace_id": str(run.trace_id) if run.trace_id else None,
            "project_id": str(run.project_id),
            "agent_id": str(run.agent_id),
            "session_id": str(run.session_id) if run.session_id else None,
            "updated_at": (
                run.completed_at.isoformat()
                if run.completed_at is not None
                else run.updated_at.isoformat()
            ),
        }

    async def resolve_run(
        self,
        target: ChatRuntimeTarget,
        *,
        preferred_run_id: UUID | None = None,
        created_after: datetime | None = None,
    ) -> ChatRunIdentity | None:
        async with self._session_factory() as session:
            if target.target_type == "agent":
                if preferred_run_id is not None:
                    run = await session.get(AgentRunModel, preferred_run_id)
                    if self._valid_agent(run, target):
                        return ChatRunIdentity(run.id, str(run.status))
                    return None

                statement = select(AgentRunModel).where(
                    AgentRunModel.project_id == target.project_id,
                    AgentRunModel.agent_id == target.target_id,
                    AgentRunModel.session_id == target.session_id,
                    AgentRunModel.agent_release_id == target.target_release_id,
                    AgentRunModel.network_execution_id.is_(None),
                )
                if created_after is None:
                    statement = statement.where(AgentRunModel.status.in_(_AGENT_ACTIVE))
                else:
                    statement = statement.where(AgentRunModel.created_at >= created_after)
                run = await session.scalar(
                    statement.order_by(
                        AgentRunModel.created_at.desc(),
                        AgentRunModel.id.desc(),
                    ).limit(1)
                )
                return (
                    ChatRunIdentity(run.id, str(run.status))
                    if self._valid_agent(run, target)
                    else None
                )

            if target.target_type != "network":
                raise ConflictError("Unsupported ChatSurface runtime target")

            if preferred_run_id is not None:
                execution = await session.get(NetworkExecutionModel, preferred_run_id)
                if self._valid_network(execution, target):
                    return ChatRunIdentity(execution.id, str(execution.status))
                return None

            statement = select(NetworkExecutionModel).where(
                NetworkExecutionModel.project_id == target.project_id,
                NetworkExecutionModel.network_id == target.target_id,
                NetworkExecutionModel.network_session_id == target.session_id,
                NetworkExecutionModel.network_version_id == target.target_release_id,
            )
            if created_after is None:
                statement = statement.where(NetworkExecutionModel.status.in_(_NETWORK_ACTIVE))
            else:
                statement = statement.where(NetworkExecutionModel.created_at >= created_after)
            execution = await session.scalar(
                statement.order_by(
                    NetworkExecutionModel.created_at.desc(),
                    NetworkExecutionModel.id.desc(),
                ).limit(1)
            )
            return (
                ChatRunIdentity(execution.id, str(execution.status))
                if self._valid_network(execution, target)
                else None
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
            if not self._valid_network(execution, runtime_request.target):
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

    async def observe(
        self,
        target: ChatRuntimeTarget,
        run_id: UUID,
        disconnect_check: DisconnectCheck,
    ) -> PreparedChatRuntime:
        async with self._session_factory() as session:
            if target.target_type == "agent":
                run = await session.get(AgentRunModel, run_id)
                if not self._valid_agent(run, target):
                    raise NotFoundError("Agent Run not found")
            elif target.target_type == "network":
                execution = await session.get(NetworkExecutionModel, run_id)
                if not self._valid_network(execution, target):
                    raise NotFoundError("Network execution not found")
            else:
                raise ConflictError("Unsupported ChatSurface runtime target")

        async def stream() -> AsyncIterator[ChatRuntimeChunk]:
            if target.target_type == "agent":
                async def durable_fallback() -> dict | None:
                    async with self._session_factory() as session:
                        latest = await session.get(AgentRunModel, run_id)
                    if not self._valid_agent(latest, target):
                        raise NotFoundError("Agent Run not found")
                    return self._agent_durable_state(latest)

                formatter = format_sse_frame
                run_ref = RunReference.agent(run_id)
                kind = "agent"
            else:
                async def durable_fallback() -> dict | None:
                    async with self._session_factory() as session:
                        latest = await session.get(NetworkExecutionModel, run_id)
                    if not self._valid_network(latest, target):
                        raise NotFoundError("Network execution not found")
                    return network_durable_state(latest)

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
        async with self._session_factory() as session:
            if target.target_type == "agent":
                run = await session.get(AgentRunModel, run_id)
                if not self._valid_agent(run, target):
                    raise NotFoundError("Agent Run not found")
                status = str(run.status)
                if status in _TERMINAL_STATUSES:
                    return ChatRunIdentity(run.id, status)
                try:
                    state = await EXECUTION_STATE_STORE.get(run_id)
                except Exception as exc:
                    raise ConflictError(
                        "Agent Run runtime control state is temporarily unavailable; "
                        "cancellation was not requested"
                    ) from exc
                if state is None:
                    raise ConflictError(
                        "Agent Run has no active runtime state; cancellation cannot be confirmed safely"
                    )
                try:
                    await EXECUTION_STATE_STORE.request_cancel(run_id)
                except Exception as exc:
                    raise ConflictError(
                        "Agent Run cancellation request could not be recorded safely"
                    ) from exc
                return ChatRunIdentity(run.id, "cancel_requested")

            if target.target_type != "network":
                raise ConflictError("Unsupported ChatSurface runtime target")
            execution = await session.get(NetworkExecutionModel, run_id)
            if not self._valid_network(execution, target):
                raise NotFoundError("Network execution not found")
            status = str(execution.status)

        if status in _TERMINAL_STATUSES:
            return ChatRunIdentity(run_id, status)
        await self._network_service().request_cancellation(run_id, target.project_id)
        return ChatRunIdentity(run_id, "cancel_requested")
