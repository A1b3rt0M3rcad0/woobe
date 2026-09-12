from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkOutboxEventModel,
    NetworkSessionModel,
)
from shared.infra.errors import ConflictError, NotFoundError
from shared.runtime.event_schema import LEGACY_STORAGE_VERSION


_ACTIVE_STATUSES = {"queued", "running", "cancel_requested"}


class NetworkRerunService:
    """Accept a new Network Run from a previous terminal execution."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        run_storage_version: str = LEGACY_STORAGE_VERSION,
    ) -> None:
        self._session_factory = session_factory
        self._run_storage_version = run_storage_version

    async def execute(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
        idempotency_key: str | None = None,
    ) -> NetworkExecutionModel:
        async with self._session_factory() as session, session.begin():
            source = await session.get(
                NetworkExecutionModel,
                execution_id,
                with_for_update=True,
            )
            if source is None or source.project_id != project_id:
                raise NotFoundError("Network execution not found")
            if source.status in _ACTIVE_STATUSES:
                raise ConflictError("An active Network execution cannot be rerun")

            if idempotency_key:
                existing = await session.scalar(
                    select(NetworkExecutionModel).where(
                        NetworkExecutionModel.network_id == source.network_id,
                        NetworkExecutionModel.idempotency_key == idempotency_key,
                    )
                )
                if existing is not None:
                    return existing

            active = await session.scalar(
                select(NetworkExecutionModel).where(
                    NetworkExecutionModel.network_session_id == source.network_session_id,
                    NetworkExecutionModel.status.in_(_ACTIVE_STATUSES),
                )
            )
            if active is not None:
                raise ConflictError(
                    f"Network Session already has an active execution: {active.id}"
                )

            network_session = await session.get(
                NetworkSessionModel,
                source.network_session_id,
                with_for_update=True,
            )
            if network_session is None or network_session.status != "active":
                raise ConflictError("Network Session is not active")

            rerun = NetworkExecutionModel(
                network_id=source.network_id,
                network_version_id=source.network_version_id,
                network_session_id=source.network_session_id,
                project_id=source.project_id,
                input_message=source.input_message,
                draft_revision=source.draft_revision,
                definition_snapshot=deepcopy(source.definition_snapshot),
                resolved_bindings_snapshot=deepcopy(source.resolved_bindings_snapshot),
                status="queued",
                storage_version=self._run_storage_version,
                idempotency_key=idempotency_key,
                last_event_sequence=1,
            )
            session.add(rerun)
            await session.flush()

            lineage = {
                "rerun_of_execution_id": str(source.id),
                "rerun_semantics": "new_logical_run",
                "session_semantics": "continue_existing_session",
                "storage_version": self._run_storage_version,
            }
            session.add_all(
                [
                    NetworkMessageModel(
                        network_session_id=source.network_session_id,
                        network_execution_id=rerun.id,
                        project_id=source.project_id,
                        role="user",
                        content=source.input_message,
                        data=lineage,
                    ),
                    NetworkExecutionEventModel(
                        network_execution_id=rerun.id,
                        network_session_id=source.network_session_id,
                        sequence=1,
                        event_type="execution_accepted",
                        payload={
                            "status": "queued",
                            "rerun_of_execution_id": str(source.id),
                            "network_version_id": (
                                str(source.network_version_id)
                                if source.network_version_id
                                else None
                            ),
                            "draft_revision": source.draft_revision,
                            "session_semantics": "continue_existing_session",
                            "storage_version": self._run_storage_version,
                        },
                    ),
                    NetworkOutboxEventModel(
                        aggregate_type="network_execution",
                        aggregate_id=rerun.id,
                        event_type="network.execution.requested.v1",
                        event_version=1,
                        routing_key=(
                            f"network.execution.{network_session.environment}.requested.v1"
                        ),
                        payload={
                            "execution_id": str(rerun.id),
                            "rerun_of_execution_id": str(source.id),
                        },
                        metadata_=lineage,
                        idempotency_key=f"network-execution:{rerun.id}:requested",
                        correlation_id=rerun.id,
                        causation_id=source.id,
                        status="pending",
                    ),
                ]
            )
            network_session.last_message_at = datetime.now(timezone.utc)
            return rerun
