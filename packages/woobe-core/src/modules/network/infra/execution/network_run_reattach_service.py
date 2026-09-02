from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from modules.network.application.dtos.observation import NetworkRunObservation
from modules.network.application.interfaces.run_reattach import DisconnectCheck
from modules.network.infra.database.runtime_repositories import NetworkRuntimeRepositories
from modules.network.infra.database.runtime_transaction_runner import (
    NetworkRuntimeTransactionRunner,
)
from shared.contracts.errors import AuthorizationError, NotFoundError, ValidationError
from shared.contracts.execution_state import ExecutionStateStore
from shared.runtime_reattach import RuntimeStreamFrame, RuntimeStreamGapError, RuntimeStreamReader
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}
_VALID_ENVIRONMENTS = {"draft", "staging", "production"}


class NetworkRunReattachService:
    """Observe Network Runs through short SQL reads plus the hot execution store.

    No database transaction survives beyond one read callback. The SSE lifetime owns
    only the runtime state reader and repeatedly reacquires durable state when needed.
    """

    def __init__(
        self,
        *,
        transactions: NetworkRuntimeTransactionRunner,
        state_store: ExecutionStateStore,
        heartbeat_seconds: float,
    ) -> None:
        self._transactions = transactions
        self._state_store = state_store
        self._heartbeat_seconds = heartbeat_seconds

    @staticmethod
    def _runtime_target(
        principal: ProjectApiPrincipal,
    ) -> tuple[str | None, UUID | None]:
        target_type = principal.target_type
        target_id = principal.target_id
        if target_type is None and principal.agent_id is not None:
            target_type = "agent"
        if target_id is None and principal.agent_id is not None:
            target_id = principal.agent_id
        return target_type, target_id

    async def _authorize_run(
        self,
        repositories: NetworkRuntimeRepositories,
        principal: object | None,
        run: NetworkRunObservation,
    ) -> None:
        if isinstance(principal, ProjectApiPrincipal):
            if principal.project_id != run.project_id:
                raise AuthorizationError("Runtime key does not belong to this Project")
            if principal.kind == "runtime":
                target_type, target_id = self._runtime_target(principal)
                if target_type != "network" or target_id != run.network_id:
                    raise NotFoundError("Network execution not found")
                if (
                    principal.environment is not None
                    and principal.environment != run.environment
                ):
                    raise NotFoundError("Network execution not found")
            return

        if isinstance(principal, AuthenticatedPrincipal):
            await repositories.project_access.require_user_access(
                user_id=principal.user_id,
                project_id=run.project_id,
            )
            return

        raise AuthorizationError("Authentication required")

    async def _load_run(
        self,
        run_id: UUID,
        principal: object | None,
    ) -> NetworkRunObservation:
        async def read_run(
            repositories: NetworkRuntimeRepositories,
        ) -> NetworkRunObservation:
            run = await repositories.runs.get(run_id)
            if run is None:
                raise NotFoundError("Network execution not found")
            await self._authorize_run(repositories, principal, run)
            return run

        return await self._transactions.read(read_run)

    @staticmethod
    def _durable_state(run: NetworkRunObservation) -> dict:
        return {
            "status": run.status,
            "output": run.output_message or "",
            "result": (
                {
                    "answer": run.output_message,
                    "parsed_output": run.parsed_output,
                    "output_parse_error": run.output_parse_error,
                    "partial": run.status == "cancelled" and bool(run.output_message),
                    "cancelled": run.status == "cancelled",
                }
                if run.output_message is not None
                or run.parsed_output is not None
                or run.output_parse_error is not None
                else None
            ),
            "parsed_output": run.parsed_output,
            "output_parse_error": run.output_parse_error,
            "trace_id": str(run.root_trace_id) if run.root_trace_id else None,
            "project_id": str(run.project_id),
            "network_id": str(run.network_id),
            "network_session_id": str(run.network_session_id),
            "input_message": run.input_message,
            "failure_code": run.failure_code,
            "failure_detail": run.failure_detail,
            "updated_at": (
                run.completed_at.isoformat()
                if run.completed_at is not None
                else run.updated_at.isoformat()
                if run.updated_at is not None
                else None
            ),
        }

    @staticmethod
    def _format_sse(frame: RuntimeStreamFrame, execution_id: UUID) -> str:
        payload = dict(frame.data)
        if frame.event_type == "run.state":
            envelope = {
                "protocol_version": 1,
                "sequence": frame.sequence,
                "execution_id": str(execution_id),
                "data": payload,
                "created_at": payload.get("updated_at"),
            }
        else:
            occurred_at = payload.pop("occurred_at", None)
            payload.pop("run_id", None)
            payload.pop("sequence", None)
            envelope = {
                "protocol_version": 1,
                "sequence": frame.sequence,
                "execution_id": str(execution_id),
                "invocation_id": payload.pop("invocation_id", None),
                "parent_invocation_id": payload.pop("parent_invocation_id", None),
                "node_id": payload.pop("node_id", None),
                "agent_id": payload.pop("agent_id", None),
                "depth": payload.pop("depth", None),
                "data": payload,
                "created_at": occurred_at,
            }
        prefix = f"id: {frame.sequence}\n" if frame.sequence is not None else ""
        return (
            f"{prefix}event: {frame.event_type}\n"
            f"data: {json.dumps(envelope, ensure_ascii=False, default=str)}\n\n"
        )

    async def authorize(
        self,
        *,
        run_id: UUID,
        principal: object | None,
    ) -> None:
        await self._load_run(run_id, principal)

    async def active(
        self,
        *,
        principal: object | None,
        network_session_id: UUID | None = None,
        network_id: UUID | None = None,
        environment: str | None = None,
    ) -> dict | None:
        if network_session_id is None and network_id is None:
            raise ValidationError("network_session_id or network_id is required")
        if environment is not None and environment not in _VALID_ENVIRONMENTS:
            raise ValidationError("environment must be draft, staging or production")

        async def read_active(repositories: NetworkRuntimeRepositories):
            run = await repositories.runs.find_active(
                network_session_id=network_session_id,
                network_id=network_id,
                environment=environment,
            )
            if run is None:
                return None
            await self._authorize_run(repositories, principal, run)
            return {
                "run_id": str(run.id),
                "execution_id": str(run.id),
                "status": run.status,
                "network_session_id": str(run.network_session_id),
                "network_id": str(run.network_id),
                "input_message": run.input_message,
                "created_at": run.created_at,
            }

        return await self._transactions.read(read_active)

    async def stream_sse(
        self,
        *,
        run_id: UUID,
        principal: object | None,
        is_disconnected: DisconnectCheck | None = None,
    ) -> AsyncIterator[str]:
        initial = await self._load_run(run_id, principal)
        reader = RuntimeStreamReader(
            self._state_store,
            heartbeat_seconds=self._heartbeat_seconds,
            block_ms=500,
        )

        async def durable_fallback() -> dict | None:
            latest = await self._load_run(run_id, principal)
            return self._durable_state(latest)

        hot = await self._state_store.get(run_id)
        if hot is None and initial.status not in _TERMINAL_STATUSES:
            queued = self._durable_state(initial)
            queued.update(
                {
                    "run_id": str(run_id),
                    "kind": "NETWORK",
                    "sequence": None,
                    "realtime_available": False,
                }
            )
            yield self._format_sse(
                RuntimeStreamFrame("run.state", queued, sequence=None),
                run_id,
            )

            while hot is None:
                if is_disconnected is not None and await is_disconnected():
                    return
                await asyncio.sleep(0.25)
                latest = await self._load_run(run_id, principal)
                if latest.status in _TERMINAL_STATUSES:
                    terminal = self._durable_state(latest)
                    terminal.update(
                        {
                            "run_id": str(run_id),
                            "kind": "NETWORK",
                            "sequence": None,
                            "realtime_available": False,
                        }
                    )
                    yield self._format_sse(
                        RuntimeStreamFrame("run.state", terminal, sequence=None),
                        run_id,
                    )
                    return
                hot = await self._state_store.get(run_id)

        try:
            async for frame in reader.stream(
                run_id,
                "network",
                durable_fallback=durable_fallback,
            ):
                if is_disconnected is not None and await is_disconnected():
                    return
                yield self._format_sse(frame, run_id)
        except RuntimeStreamGapError:
            latest = await self._load_run(run_id, principal)
            state = self._durable_state(latest)
            state.update(
                {
                    "run_id": str(run_id),
                    "kind": "NETWORK",
                    "sequence": None,
                    "realtime_available": False,
                    "degraded_reason": "runtime_event_gap",
                }
            )
            yield self._format_sse(
                RuntimeStreamFrame("run.state", state, sequence=None),
                run_id,
            )
