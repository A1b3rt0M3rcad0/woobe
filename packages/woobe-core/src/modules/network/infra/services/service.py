from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.network.infra.services.session_mode_binding_service import (
    NetworkApplicationService as SessionModeNetworkApplicationService,
)
from modules.network.domain.enums import NetworkEnvironment
from modules.network.domain.graph import composition_hash
from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkModel,
    NetworkOutboxEventModel,
    NetworkSessionModel,
    NetworkVersionModel,
)
from shared.infra.errors import ConflictError, NotFoundError, ValidationError
from shared.runtime.event_schema import LEGACY_STORAGE_VERSION


_TERMINAL_EXECUTION_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "timed_out",
    "uncertain",
}
_ACTIVE_EXECUTION_STATUSES = {"queued", "running", "cancel_requested"}


class NetworkApplicationService(SessionModeNetworkApplicationService):
    """Executes every immutable Network Session against its opening version."""

    def __init__(
        self,
        *args,
        runtime_control: Any | None = None,
        run_storage_version: str = LEGACY_STORAGE_VERSION,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if runtime_control is None:
            # Transitional default until Network composition owns this dependency.
            from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
            from shared.composition_resources import EXECUTION_STATE_STORE

            runtime_control = RedisNetworkExecutionStore(EXECUTION_STATE_STORE)
        self._runtime_control = runtime_control
        self._run_storage_version = run_storage_version

    async def submit_execution(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        network_session_id: UUID,
        message: str,
        idempotency_key: str | None,
        expected_draft_revision: int | None = None,
    ) -> NetworkExecutionModel:
        if not message.strip():
            raise ValidationError("Network message cannot be blank")

        async with self._session_factory() as session, session.begin():
            network_session = await session.get(
                NetworkSessionModel,
                network_session_id,
                with_for_update=True,
            )
            if (
                network_session is None
                or network_session.network_id != network_id
                or network_session.project_id != project_id
                or network_session.status != "active"
            ):
                raise NotFoundError("Network Session not found")

            if idempotency_key:
                existing = await session.scalar(
                    select(NetworkExecutionModel).where(
                        NetworkExecutionModel.network_id == network_id,
                        NetworkExecutionModel.idempotency_key == idempotency_key,
                    )
                )
                if existing is not None:
                    return existing

            active_execution = await session.scalar(
                select(NetworkExecutionModel).where(
                    NetworkExecutionModel.network_session_id == network_session_id,
                    NetworkExecutionModel.status.in_(
                        {"queued", "running", "cancel_requested"}
                    ),
                )
            )
            if active_execution is not None:
                raise ConflictError(
                    f"Network Session already has an active execution: {active_execution.id}"
                )

            draft_revision: int | None = None
            definition_snapshot: dict[str, Any] | None = None
            bindings_snapshot: dict[str, Any] | None = None
            accepted_version_id: UUID | None = network_session.network_version_id
            accepted_version: str | None = None

            if network_session.environment == NetworkEnvironment.DRAFT.value:
                network = await session.get(NetworkModel, network_id, with_for_update=True)
                if network is None or network.project_id != project_id:
                    raise NotFoundError("Network not found")
                if (
                    expected_draft_revision is not None
                    and expected_draft_revision != network.draft_revision
                ):
                    raise ConflictError(
                        "Network Draft changed before the execution was accepted"
                    )
                definition = self._definition(network.draft_definition)
                bindings_snapshot = await self._resolve_draft_bindings(
                    session,
                    definition,
                    project_id,
                )
                draft_revision = network.draft_revision
                definition_snapshot = definition.to_dict()
                accepted_composition_hash = composition_hash(
                    definition,
                    bindings_snapshot,
                )
            else:
                if accepted_version_id is None:
                    raise ConflictError("Pinned Network version was not found")
                version = await session.get(
                    NetworkVersionModel,
                    accepted_version_id,
                )
                if (
                    version is None
                    or version.network_id != network_id
                    or version.project_id != project_id
                ):
                    raise ConflictError("Pinned Network version was not found")
                definition = self._definition(version.definition)
                accepted_version = version.version
                accepted_composition_hash = version.composition_hash

            execution = NetworkExecutionModel(
                network_id=network_id,
                network_version_id=accepted_version_id,
                network_session_id=network_session_id,
                project_id=project_id,
                input_message=message.strip(),
                draft_revision=draft_revision,
                definition_snapshot=definition_snapshot,
                resolved_bindings_snapshot=bindings_snapshot,
                status="queued",
                storage_version=self._run_storage_version,
                idempotency_key=idempotency_key,
                last_event_sequence=1,
            )
            session.add(execution)
            await session.flush()

            chat_surface_id = (
                str(network_session.chat_surface_id)
                if network_session.chat_surface_id is not None
                else None
            )
            attribution = {
                "origin": network_session.origin,
                "chat_surface_id": chat_surface_id,
                "network_session_id": str(network_session.id),
                "network_version_id": (
                    str(accepted_version_id) if accepted_version_id else None
                ),
            }
            session.add_all(
                [
                    NetworkMessageModel(
                        network_session_id=network_session_id,
                        network_execution_id=execution.id,
                        project_id=project_id,
                        role="user",
                        content=message.strip(),
                        data=attribution if chat_surface_id else None,
                    ),
                    NetworkExecutionEventModel(
                        network_execution_id=execution.id,
                        network_session_id=network_session_id,
                        sequence=1,
                        event_type="execution_accepted",
                        payload={
                            "status": "queued",
                            "environment": network_session.environment,
                            "draft_revision": draft_revision,
                            "network_version_id": (
                                str(accepted_version_id)
                                if accepted_version_id
                                else None
                            ),
                            "network_version": accepted_version,
                            "composition_hash": accepted_composition_hash,
                            "root_node_id": str(definition.root_node_id),
                            "origin": network_session.origin,
                            "chat_surface_id": chat_surface_id,
                            "storage_version": self._run_storage_version,
                            "limits": {
                                "max_depth": definition.limits.max_depth,
                                "max_invocations": definition.limits.max_invocations,
                                "timeout_seconds": definition.limits.timeout_seconds,
                            },
                        },
                    ),
                    NetworkOutboxEventModel(
                        aggregate_type="network_execution",
                        aggregate_id=execution.id,
                        event_type="network.execution.requested.v1",
                        event_version=1,
                        routing_key=(
                            f"network.execution.{network_session.environment}.requested.v1"
                        ),
                        payload={"execution_id": str(execution.id)},
                        metadata_=attribution if chat_surface_id else None,
                        idempotency_key=f"network-execution:{execution.id}:requested",
                        correlation_id=execution.id,
                        causation_id=None,
                        status="pending",
                    ),
                ]
            )
            network_session.last_message_at = datetime.now(timezone.utc)
            return execution

    async def request_cancellation(self, execution_id: UUID, project_id: UUID) -> None:
        """Cancel through Redis once operational execution exists.

        PostgreSQL may remain `queued` for the whole hot execution, so it cannot be
        used to decide whether a Run has already started. Redis owns that fact.
        """

        async with self._session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            if execution is None or execution.project_id != project_id:
                raise NotFoundError("Network execution not found")
            durable_status = str(execution.status)

        if durable_status in _TERMINAL_EXECUTION_STATUSES:
            return

        state = await self._runtime_control.snapshot(execution_id)
        if state:
            runtime_status = str(state.get("status") or "")
            if (
                runtime_status == "terminal_pending_persist"
                or state.get("phase") == "persisted"
                or runtime_status in _TERMINAL_EXECUTION_STATUSES
            ):
                return
            await self._runtime_control.request_cancel(execution_id)
            return

        await super().request_cancellation(execution_id, project_id)

        state = await self._runtime_control.snapshot(execution_id)
        if state:
            runtime_status = str(state.get("status") or "")
            if (
                runtime_status != "terminal_pending_persist"
                and state.get("phase") != "persisted"
                and runtime_status not in _TERMINAL_EXECUTION_STATUSES
            ):
                await self._runtime_control.request_cancel(execution_id)

    @staticmethod
    def _matches_chat_surface_target(
        execution: NetworkExecutionModel | None,
        *,
        project_id: UUID,
        network_id: UUID,
        network_session_id: UUID,
        network_version_id: UUID,
    ) -> bool:
        return bool(
            execution is not None
            and execution.project_id == project_id
            and execution.network_id == network_id
            and execution.network_session_id == network_session_id
            and execution.network_version_id == network_version_id
        )

    async def resolve_chat_surface_run(
        self,
        *,
        project_id: UUID,
        network_id: UUID,
        network_session_id: UUID,
        network_version_id: UUID,
        preferred_run_id: UUID | None = None,
        created_after: datetime | None = None,
    ) -> dict[str, object] | None:
        async with self._session_factory() as session:
            statement = select(NetworkExecutionModel).where(
                NetworkExecutionModel.project_id == project_id,
                NetworkExecutionModel.network_id == network_id,
                NetworkExecutionModel.network_session_id == network_session_id,
                NetworkExecutionModel.network_version_id == network_version_id,
            )
            if preferred_run_id is not None:
                statement = statement.where(NetworkExecutionModel.id == preferred_run_id)
            elif created_after is not None:
                statement = statement.where(
                    NetworkExecutionModel.created_at >= created_after
                )
            else:
                statement = statement.where(
                    NetworkExecutionModel.status.in_(_ACTIVE_EXECUTION_STATUSES)
                )
            execution = await session.scalar(
                statement.order_by(
                    NetworkExecutionModel.created_at.desc(),
                    NetworkExecutionModel.id.desc(),
                ).limit(1)
            )
        if not self._matches_chat_surface_target(
            execution,
            project_id=project_id,
            network_id=network_id,
            network_session_id=network_session_id,
            network_version_id=network_version_id,
        ):
            return None
        return {"run_id": execution.id, "status": str(execution.status)}

    async def chat_surface_durable_state(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
        network_id: UUID,
        network_session_id: UUID,
        network_version_id: UUID,
    ) -> dict[str, object]:
        async with self._session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
        if not self._matches_chat_surface_target(
            execution,
            project_id=project_id,
            network_id=network_id,
            network_session_id=network_session_id,
            network_version_id=network_version_id,
        ):
            raise NotFoundError("Network execution not found")
        result = (
            {
                "answer": execution.output_message,
                "parsed_output": execution.parsed_output,
                "output_parse_error": execution.output_parse_error,
                "partial": str(execution.status) == "cancelled"
                and bool(execution.output_message),
                "cancelled": str(execution.status) == "cancelled",
            }
            if execution.output_message is not None
            or execution.parsed_output is not None
            or execution.output_parse_error is not None
            else None
        )
        updated_at = execution.completed_at or execution.updated_at
        return {
            "status": str(execution.status),
            "output": execution.output_message or "",
            "result": result,
            "parsed_output": execution.parsed_output,
            "output_parse_error": execution.output_parse_error,
            "trace_id": str(execution.root_trace_id) if execution.root_trace_id else None,
            "project_id": str(execution.project_id),
            "network_id": str(execution.network_id),
            "network_session_id": str(execution.network_session_id),
            "input_message": execution.input_message,
            "failure_code": execution.failure_code,
            "failure_detail": execution.failure_detail,
            "updated_at": updated_at.isoformat() if updated_at is not None else None,
        }


__all__ = ["NetworkApplicationService"]
