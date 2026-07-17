from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.network.domain.enums import NetworkExecutionStatus
from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkInvocationModel,
    NetworkMessageModel,
    NetworkModel,
    NetworkOutboxEventModel,
    NetworkSessionModel,
    NetworkVersionModel,
)
from shared.infra.errors import ConflictError


class NetworkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_project(self, project_id: UUID) -> list[NetworkModel]:
        result = await self.session.execute(
            select(NetworkModel)
            .where(NetworkModel.project_id == project_id)
            .order_by(NetworkModel.updated_at.desc(), NetworkModel.created_at.desc())
        )
        return list(result.scalars())

    async def get_by_project(self, project_id: UUID) -> NetworkModel | None:
        networks = await self.list_by_project(project_id)
        if not networks:
            return None
        if len(networks) > 1:
            raise ConflictError(
                "Multiple Networks exist in this Project; select a Network explicitly"
            )
        return networks[0]

    async def get(self, network_id: UUID) -> NetworkModel | None:
        return await self.session.get(NetworkModel, network_id)

    async def get_for_project(
        self, network_id: UUID, project_id: UUID
    ) -> NetworkModel | None:
        return await self.session.scalar(
            select(NetworkModel).where(
                NetworkModel.id == network_id,
                NetworkModel.project_id == project_id,
            )
        )

    async def get_version(self, version_id: UUID) -> NetworkVersionModel | None:
        return await self.session.get(NetworkVersionModel, version_id)

    async def list_versions(self, network_id: UUID) -> list[NetworkVersionModel]:
        result = await self.session.execute(
            select(NetworkVersionModel)
            .where(NetworkVersionModel.network_id == network_id)
            .order_by(NetworkVersionModel.created_at.desc())
        )
        return list(result.scalars())

    async def save_draft(
        self,
        network_id: UUID,
        *,
        expected_revision: int,
        name: str,
        description: str,
        definition: dict[str, Any],
    ) -> NetworkModel | None:
        network = await self.get(network_id)
        if network is None:
            return None

        from modules.agent.infra.database.models import AgentModel

        node_agent_ids = [
            UUID(str(node["agent_id"]))
            for node in definition.get("nodes", [])
            if node.get("agent_id")
        ]
        if len(node_agent_ids) != len(set(node_agent_ids)):
            raise ConflictError(
                "The same Agent cannot appear more than once in a Network Draft"
            )
        referenced_agent_ids = set(node_agent_ids)
        if referenced_agent_ids:
            result = await self.session.execute(
                select(AgentModel.id).where(
                    AgentModel.id.in_(referenced_agent_ids),
                    AgentModel.project_id == network.project_id,
                    AgentModel.status == "active",
                )
            )
            available_agent_ids = set(result.scalars())
            unavailable_agent_ids = referenced_agent_ids - available_agent_ids
            if unavailable_agent_ids:
                joined = ", ".join(
                    sorted(str(agent_id) for agent_id in unavailable_agent_ids)
                )
                raise ConflictError(
                    f"Network Draft references inactive or unavailable Agents: {joined}"
                )

        # Network metadata is persisted through the dedicated resource endpoint.
        # Draft saves only mutate the versioned composition and its revision.
        _ = (name, description)
        statement = (
            update(NetworkModel)
            .where(
                NetworkModel.id == network_id,
                NetworkModel.project_id == network.project_id,
                NetworkModel.draft_revision == expected_revision,
            )
            .values(
                draft_definition=definition,
                draft_revision=NetworkModel.draft_revision + 1,
            )
            .returning(NetworkModel)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()


class NetworkRuntimeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_session(self, session_id: UUID) -> NetworkSessionModel | None:
        return await self.session.get(NetworkSessionModel, session_id)

    async def get_execution(self, execution_id: UUID) -> NetworkExecutionModel | None:
        return await self.session.get(NetworkExecutionModel, execution_id)

    async def list_events_after(
        self,
        execution_id: UUID,
        sequence: int,
        *,
        limit: int = 500,
    ) -> list[NetworkExecutionEventModel]:
        result = await self.session.execute(
            select(NetworkExecutionEventModel)
            .where(
                NetworkExecutionEventModel.network_execution_id == execution_id,
                NetworkExecutionEventModel.sequence > sequence,
            )
            .order_by(NetworkExecutionEventModel.sequence.asc())
            .limit(limit)
        )
        return list(result.scalars())

    async def append_event(
        self,
        execution: NetworkExecutionModel,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        invocation: NetworkInvocationModel | None = None,
    ) -> NetworkExecutionEventModel:
        execution.last_event_sequence += 1
        event = NetworkExecutionEventModel(
            network_execution_id=execution.id,
            network_session_id=execution.network_session_id,
            sequence=execution.last_event_sequence,
            event_type=event_type,
            invocation_id=invocation.id if invocation else None,
            parent_invocation_id=invocation.parent_invocation_id
            if invocation
            else None,
            node_id=invocation.node_id if invocation else None,
            agent_id=invocation.agent_id if invocation else None,
            depth=invocation.depth if invocation else None,
            payload=payload or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def claim_execution(
        self,
        execution_id: UUID,
        *,
        worker_id: str,
        lease_ttl_seconds: int,
    ) -> NetworkExecutionModel | None:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            update(NetworkExecutionModel)
            .where(
                NetworkExecutionModel.id == execution_id,
                NetworkExecutionModel.status == NetworkExecutionStatus.QUEUED.value,
            )
            .values(
                status=NetworkExecutionStatus.RUNNING.value,
                lease_owner=worker_id,
                lease_generation=NetworkExecutionModel.lease_generation + 1,
                lease_expires_at=now + timedelta(seconds=lease_ttl_seconds),
                heartbeat_at=now,
                started_at=func.coalesce(NetworkExecutionModel.started_at, now),
                attempt=NetworkExecutionModel.attempt + 1,
            )
            .returning(NetworkExecutionModel)
        )
        return result.scalar_one_or_none()

    async def renew_lease(
        self,
        execution_id: UUID,
        *,
        worker_id: str,
        generation: int,
        lease_ttl_seconds: int,
    ) -> bool:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            update(NetworkExecutionModel)
            .where(
                NetworkExecutionModel.id == execution_id,
                NetworkExecutionModel.status == NetworkExecutionStatus.RUNNING.value,
                NetworkExecutionModel.lease_owner == worker_id,
                NetworkExecutionModel.lease_generation == generation,
            )
            .values(
                heartbeat_at=now,
                lease_expires_at=now + timedelta(seconds=lease_ttl_seconds),
            )
        )
        return bool(result.rowcount)

    async def get_or_create_agent_context(
        self,
        *,
        network_session_id: UUID,
        node_id: UUID,
        agent_id: UUID,
    ) -> NetworkAgentContextModel:
        result = await self.session.execute(
            select(NetworkAgentContextModel).where(
                NetworkAgentContextModel.network_session_id == network_session_id,
                NetworkAgentContextModel.network_node_id == node_id,
            )
        )
        context = result.scalar_one_or_none()
        if context is not None:
            if context.agent_id != agent_id:
                context.agent_id = agent_id
                context.agent_session_id = None
            return context
        context = NetworkAgentContextModel(
            network_session_id=network_session_id,
            network_node_id=node_id,
            agent_id=agent_id,
            agent_session_id=None,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(context)
                await self.session.flush()
            return context
        except IntegrityError:
            result = await self.session.execute(
                select(NetworkAgentContextModel).where(
                    NetworkAgentContextModel.network_session_id == network_session_id,
                    NetworkAgentContextModel.network_node_id == node_id,
                )
            )
            return result.scalar_one()

    async def create_invocation(
        self,
        *,
        execution: NetworkExecutionModel,
        node_id: UUID,
        agent_id: UUID,
        depth: int,
        input_message: str,
        parent_invocation_id: UUID | None,
        agent_session_id: UUID | None,
    ) -> NetworkInvocationModel:
        invocation = NetworkInvocationModel(
            network_execution_id=execution.id,
            network_session_id=execution.network_session_id,
            parent_invocation_id=parent_invocation_id,
            node_id=node_id,
            agent_id=agent_id,
            agent_session_id=agent_session_id,
            trace_id=None,
            depth=depth,
            status="running",
            input_message=input_message,
        )
        self.session.add(invocation)
        await self.session.flush()
        return invocation

    async def mark_completed(
        self,
        execution: NetworkExecutionModel,
        *,
        output: str,
        root_trace_id: UUID | None,
    ) -> None:
        now = datetime.now(timezone.utc)
        execution.status = NetworkExecutionStatus.COMPLETED.value
        execution.output_message = output
        execution.root_trace_id = root_trace_id
        execution.completed_at = now
        execution.lease_owner = None
        execution.lease_expires_at = None
        self.session.add(
            NetworkMessageModel(
                network_session_id=execution.network_session_id,
                network_execution_id=execution.id,
                project_id=execution.project_id,
                role="assistant",
                content=output,
                data={"trace_id": str(root_trace_id) if root_trace_id else None},
            )
        )

    async def mark_failed(
        self,
        execution: NetworkExecutionModel,
        *,
        code: str,
        detail: str,
        root_trace_id: UUID | None = None,
        uncertain: bool = False,
    ) -> None:
        execution.status = (
            NetworkExecutionStatus.UNCERTAIN.value
            if uncertain
            else NetworkExecutionStatus.FAILED.value
        )
        execution.failure_code = code
        execution.failure_detail = detail[:4000]
        if root_trace_id is not None:
            execution.root_trace_id = root_trace_id
        execution.completed_at = datetime.now(timezone.utc)
        execution.lease_owner = None
        execution.lease_expires_at = None


class NetworkOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim_batch(
        self, *, limit: int, worker_id: str
    ) -> list[NetworkOutboxEventModel]:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(NetworkOutboxEventModel)
            .where(
                NetworkOutboxEventModel.status.in_(["pending", "retryable"]),
                NetworkOutboxEventModel.available_at <= now,
            )
            .order_by(NetworkOutboxEventModel.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        events = list(result.scalars())
        for event in events:
            event.locked_at = now
            event.locked_by = worker_id
        return events

    async def mark_published(self, event: NetworkOutboxEventModel) -> None:
        event.status = "published"
        event.published_at = datetime.now(timezone.utc)
        event.locked_at = None
        event.locked_by = None

    async def mark_retryable(self, event: NetworkOutboxEventModel, error: str) -> None:
        event.attempts += 1
        event.status = "dead" if event.attempts >= 5 else "retryable"
        event.error = error[:4000]
        event.available_at = datetime.now(timezone.utc) + timedelta(
            seconds=min(300, 2**event.attempts)
        )
        event.locked_at = None
        event.locked_by = None
