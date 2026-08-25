from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.network.application.session_mode_binding_service import (
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


_TERMINAL_EXECUTION_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "timed_out",
    "uncertain",
}


class NetworkApplicationService(SessionModeNetworkApplicationService):
    """Executes every immutable Network Session against its opening version."""

    def __init__(self, *args, runtime_control: Any | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if runtime_control is None:
            # Transitional default until Network composition owns this dependency.
            # Application receives only the operational control surface at runtime;
            # PostgreSQL remains the durable source of truth.
            from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
            from shared.composition_resources import EXECUTION_STATE_STORE

            runtime_control = RedisNetworkExecutionStore(EXECUTION_STATE_STORE)
        self._runtime_control = runtime_control

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

        # No operational state exists yet. Preserve the legacy durable cancellation
        # for an execution that is still waiting for the broker/worker.
        await super().request_cancellation(execution_id, project_id)

        # Close the only relevant race: the worker may have initialized Redis after
        # the first lookup but before PostgreSQL was marked cancelled.
        state = await self._runtime_control.snapshot(execution_id)
        if state:
            runtime_status = str(state.get("status") or "")
            if (
                runtime_status != "terminal_pending_persist"
                and state.get("phase") != "persisted"
                and runtime_status not in _TERMINAL_EXECUTION_STATUSES
            ):
                await self._runtime_control.request_cancel(execution_id)


__all__ = ["NetworkApplicationService"]
