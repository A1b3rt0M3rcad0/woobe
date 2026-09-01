from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.network.domain.entities import NetworkDefinition
from modules.network.domain.enums import NetworkEnvironment, NetworkVersionKind
from modules.network.domain.graph import composition_hash, validate_network_definition
from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkModel,
    NetworkOutboxEventModel,
    NetworkSessionModel,
    NetworkVersionModel,
)
from modules.network.infra.database.repositories import NetworkRepository
from shared.infra.errors import ConflictError, NotFoundError, ValidationError


class NetworkApplicationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        hard_max_depth: int = 8,
        hard_max_invocations: int = 64,
        hard_timeout_seconds: int = 300,
    ) -> None:
        self._session_factory = session_factory
        self._hard_max_depth = hard_max_depth
        self._hard_max_invocations = hard_max_invocations
        self._hard_timeout_seconds = hard_timeout_seconds

    async def ensure_network(self, project_id: UUID, name: str) -> NetworkModel:
        async with self._session_factory() as session:
            repository = NetworkRepository(session)
            existing = await repository.get_by_project(project_id)
            if existing is not None:
                return existing
            network = NetworkModel(
                project_id=project_id,
                name=name.strip() or "Project Network",
                description="",
                draft_definition={},
                draft_revision=0,
            )
            session.add(network)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                existing = await repository.get_by_project(project_id)
                if existing is None:
                    raise
                return existing
            await session.refresh(network)
            return network

    async def get_network(self, project_id: UUID) -> NetworkModel:
        async with self._session_factory() as session:
            network = await NetworkRepository(session).get_by_project(project_id)
            if network is None:
                raise NotFoundError("Network not found")
            return network

    def _definition(self, value: dict[str, Any]) -> NetworkDefinition:
        try:
            definition = NetworkDefinition.from_dict(value)
            validate_network_definition(
                definition,
                hard_max_depth=self._hard_max_depth,
                hard_max_invocations=self._hard_max_invocations,
                hard_timeout_seconds=self._hard_timeout_seconds,
            )
            return definition
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(str(exc)) from exc

    async def save_draft(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        expected_revision: int,
        name: str,
        description: str,
        definition: dict[str, Any],
    ) -> NetworkModel:
        parsed = self._definition(definition)
        async with self._session_factory() as session, session.begin():
            repository = NetworkRepository(session)
            network = await repository.get(network_id)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network not found")
            saved = await repository.save_draft(
                network_id,
                expected_revision=expected_revision,
                name=name.strip() or network.name,
                description=description.strip(),
                definition=parsed.to_dict(),
            )
            if saved is None:
                raise ConflictError("Network Draft was changed by another request")
            return saved

    async def preview_promotion(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: NetworkEnvironment,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            network = await NetworkRepository(session).get(network_id)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network not found")
            definition = await self._promotion_definition(
                session,
                network,
                environment,
            )
            status = environment.value
            bindings = await self._resolve_agent_bindings(
                session, definition, project_id, status
            )
            missing = [item for item in bindings.values() if not item.get("release_id")]
            return {
                "environment": environment.value,
                "ready": not missing,
                "bindings": bindings,
                "missing_agent_ids": [item["agent_id"] for item in missing],
            }

    async def promote(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: NetworkEnvironment,
        created_by: UUID | None,
    ) -> NetworkVersionModel:
        async with self._session_factory() as session, session.begin():
            network = await session.get(NetworkModel, network_id, with_for_update=True)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network not found")
            definition = await self._promotion_definition(
                session,
                network,
                environment,
            )
            status = environment.value
            bindings = await self._resolve_agent_bindings(
                session, definition, project_id, status
            )
            missing = [
                item["agent_id"]
                for item in bindings.values()
                if not item.get("release_id")
            ]
            if missing:
                raise ConflictError(
                    f"Agents are not ready for {status}: {', '.join(missing)}"
                )

            kind = (
                NetworkVersionKind.STAGING
                if environment == NetworkEnvironment.STAGING
                else NetworkVersionKind.RELEASE
            )
            count = await session.scalar(
                select(func.count(NetworkVersionModel.id)).where(
                    NetworkVersionModel.network_id == network.id,
                    NetworkVersionModel.kind == kind.value,
                )
            )
            now = datetime.now(timezone.utc)
            version_name = f"v{int(count or 0) + 1}.{now:%Y%m%d.%H%M%S}"
            version = NetworkVersionModel(
                network_id=network.id,
                project_id=project_id,
                kind=kind.value,
                version=version_name,
                definition=definition.to_dict(),
                resolved_bindings=bindings,
                composition_hash=composition_hash(definition, bindings),
                created_by=created_by,
            )
            session.add(version)
            await session.flush()
            if environment == NetworkEnvironment.STAGING:
                network.staging_version_id = version.id
            else:
                network.production_version_id = version.id
            return version

    async def _promotion_definition(
        self,
        session: AsyncSession,
        network: NetworkModel,
        environment: NetworkEnvironment,
    ) -> NetworkDefinition:
        if environment == NetworkEnvironment.STAGING:
            return self._definition(network.draft_definition)
        if environment != NetworkEnvironment.PRODUCTION:
            raise ValidationError("Draft cannot be promoted as a runtime environment")
        if network.staging_version_id is None:
            raise ConflictError("Stage the Network before publishing Production")
        staging = await session.get(NetworkVersionModel, network.staging_version_id)
        if staging is None or staging.network_id != network.id or staging.kind != "staging":
            raise ConflictError("Current Network Staging version was not found")
        return self._definition(staging.definition)

    async def _resolve_agent_bindings(
        self,
        session: AsyncSession,
        definition: NetworkDefinition,
        project_id: UUID,
        status: str,
    ) -> dict[str, dict[str, Any]]:
        # Cross-module references are intentionally logical. Network never owns
        # Agent rows and therefore does not create a cross-module foreign key.
        from modules.agent.infra.database.models import AgentReleaseModel

        bindings: dict[str, dict[str, Any]] = {}
        for node in definition.nodes:
            result = await session.execute(
                select(AgentReleaseModel)
                .where(
                    AgentReleaseModel.project_id == project_id,
                    AgentReleaseModel.agent_id == node.agent_id,
                    AgentReleaseModel.status == status,
                )
                .order_by(AgentReleaseModel.created_at.desc())
                .limit(1)
            )
            release = result.scalar_one_or_none()
            bindings[str(node.id)] = {
                "node_id": str(node.id),
                "agent_id": str(node.agent_id),
                "release_id": str(release.id) if release else None,
                "release_version": release.version if release else None,
                "release_status": release.status if release else None,
            }
        return bindings

    @staticmethod
    def _uuid_text(value: Any) -> str | None:
        return str(value) if value else None

    async def _resolve_draft_bindings(
        self,
        session: AsyncSession,
        definition: NetworkDefinition,
        project_id: UUID,
    ) -> dict[str, dict[str, Any]]:
        """Capture the current Agent Draft configuration for one execution.

        A Draft Network Session remains mutable. The copied binding below is
        stored on NetworkExecution so a queued or running execution never
        observes edits made after it was accepted.
        """
        from modules.agent.infra.database.models import AgentModel, AgentReleaseModel

        bindings: dict[str, dict[str, Any]] = {}
        for node in definition.nodes:
            agent = await session.scalar(
                select(AgentModel).where(
                    AgentModel.id == node.agent_id,
                    AgentModel.project_id == project_id,
                    AgentModel.status == "active",
                )
            )
            if agent is None:
                raise ConflictError(f"Agent Draft is unavailable: {node.agent_id}")

            draft_release = await session.scalar(
                select(AgentReleaseModel)
                .where(
                    AgentReleaseModel.project_id == project_id,
                    AgentReleaseModel.agent_id == node.agent_id,
                    AgentReleaseModel.status == "draft",
                )
                .order_by(AgentReleaseModel.updated_at.desc())
                .limit(1)
            )
            agent_settings = dict(agent.settings or {})
            runtime_config = deepcopy(
                getattr(draft_release, "runtime_config", None)
                or agent_settings.get("runtime_config")
            )
            snapshot = {
                "system_prompt": (
                    draft_release.system_prompt
                    if draft_release is not None
                    and draft_release.system_prompt is not None
                    else agent.system_prompt
                ),
                "response_format": (
                    draft_release.response_format
                    if draft_release is not None
                    and draft_release.response_format is not None
                    else agent_settings.get("response_format")
                ),
                "provider": (
                    draft_release.provider
                    if draft_release is not None and draft_release.provider is not None
                    else agent.provider
                ),
                "model": (
                    draft_release.model
                    if draft_release is not None and draft_release.model is not None
                    else agent.model
                ),
                "provider_credential_id": self._uuid_text(
                    draft_release.provider_credential_id
                    if draft_release is not None
                    and draft_release.provider_credential_id is not None
                    else agent.provider_credential_id
                ),
                "provider_model_id": self._uuid_text(
                    getattr(draft_release, "provider_model_id", None)
                    or getattr(agent, "provider_model_id", None)
                ),
                "fallback_provider": (
                    draft_release.fallback_provider
                    if draft_release is not None
                    and draft_release.fallback_provider is not None
                    else agent.fallback_provider
                ),
                "fallback_model": (
                    draft_release.fallback_model
                    if draft_release is not None
                    and draft_release.fallback_model is not None
                    else agent.fallback_model
                ),
                "fallback_credential_id": self._uuid_text(
                    draft_release.fallback_credential_id
                    if draft_release is not None
                    and draft_release.fallback_credential_id is not None
                    else agent.fallback_credential_id
                ),
                "fallback_provider_model_id": self._uuid_text(
                    getattr(draft_release, "fallback_provider_model_id", None)
                    or getattr(agent, "fallback_provider_model_id", None)
                ),
                "temperature": (
                    draft_release.temperature
                    if draft_release is not None
                    and draft_release.temperature is not None
                    else agent.temperature
                ),
                "max_output_tokens": (
                    draft_release.max_output_tokens
                    if draft_release is not None
                    and draft_release.max_output_tokens is not None
                    else agent.max_output_tokens
                ),
                "session_mode": (
                    draft_release.session_mode
                    if draft_release is not None
                    and draft_release.session_mode is not None
                    else agent.session_mode
                ),
                "runtime_config": runtime_config,
            }
            bindings[str(node.id)] = {
                "node_id": str(node.id),
                "agent_id": str(node.agent_id),
                "draft_release_id": self._uuid_text(
                    draft_release.id if draft_release is not None else None
                ),
                "snapshot_override": snapshot,
            }
        return bindings

    async def list_versions(
        self, network_id: UUID, project_id: UUID
    ) -> list[NetworkVersionModel]:
        async with self._session_factory() as session:
            network = await NetworkRepository(session).get(network_id)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network not found")
            return await NetworkRepository(session).list_versions(network_id)

    async def rollback_production(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        target_version_id: UUID,
        created_by: UUID | None,
    ) -> NetworkVersionModel:
        async with self._session_factory() as session, session.begin():
            network = await session.get(NetworkModel, network_id, with_for_update=True)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network not found")
            target = await session.get(NetworkVersionModel, target_version_id)
            if (
                target is None
                or target.network_id != network.id
                or target.project_id != project_id
                or target.kind != NetworkVersionKind.RELEASE.value
            ):
                raise NotFoundError("Historical Network Production version not found")
            if target.id == network.production_version_id:
                raise ConflictError("Selected Network version is already in Production")
            count = await session.scalar(
                select(func.count(NetworkVersionModel.id)).where(
                    NetworkVersionModel.network_id == network.id,
                    NetworkVersionModel.kind == NetworkVersionKind.RELEASE.value,
                )
            )
            now = datetime.now(timezone.utc)
            version = NetworkVersionModel(
                network_id=network.id,
                project_id=project_id,
                kind=NetworkVersionKind.RELEASE.value,
                version=f"v{int(count or 0) + 1}.{now:%Y%m%d.%H%M%S}",
                definition=deepcopy(target.definition),
                resolved_bindings=deepcopy(target.resolved_bindings),
                composition_hash=target.composition_hash,
                created_by=created_by,
                rollback_of_version_id=target.id,
            )
            session.add(version)
            await session.flush()
            network.production_version_id = version.id
            return version

    async def create_session(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: NetworkEnvironment,
        title: str,
        tenant_id: str | None,
        user_id: str | None,
        external_session_id: str | None,
    ) -> NetworkSessionModel:
        async with self._session_factory() as session, session.begin():
            network = await NetworkRepository(session).get(network_id)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network not found")
            if environment == NetworkEnvironment.DRAFT:
                self._definition(network.draft_definition)
                version_id = None
            else:
                version_id = (
                    network.staging_version_id
                    if environment == NetworkEnvironment.STAGING
                    else network.production_version_id
                )
                if version_id is None:
                    raise ConflictError(f"Network {environment.value} is not ready")
            network_session = NetworkSessionModel(
                network_id=network.id,
                network_version_id=version_id,
                project_id=project_id,
                environment=environment.value,
                title=title.strip() or "New Network session",
                tenant_id=tenant_id,
                user_id=user_id,
                external_session_id=external_session_id,
                status="active",
            )
            session.add(network_session)
            await session.flush()
            return network_session

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
            if (
                network_session.origin == "chat_surface"
                and network_session.environment == NetworkEnvironment.PRODUCTION.value
            ):
                network = await session.get(NetworkModel, network_id, with_for_update=True)
                if network is None or network.project_id != project_id:
                    raise NotFoundError("Network not found")
                accepted_version_id = network.production_version_id
                if accepted_version_id is None:
                    raise ConflictError("Network Production is not ready")
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
                version = await session.get(
                    NetworkVersionModel,
                    accepted_version_id,
                )
                if version is None or version.network_id != network_id:
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
            session.add_all(
                [
                    NetworkMessageModel(
                        network_session_id=network_session_id,
                        network_execution_id=execution.id,
                        project_id=project_id,
                        role="user",
                        content=message.strip(),
                        data=None,
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
                            "network_version_id": str(accepted_version_id)
                            if accepted_version_id
                            else None,
                            "network_version": accepted_version,
                            "composition_hash": accepted_composition_hash,
                            "root_node_id": str(definition.root_node_id),
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
                        routing_key=f"network.execution.{network_session.environment}.requested.v1",
                        payload={"execution_id": str(execution.id)},
                        metadata_=None,
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
        async with self._session_factory() as session, session.begin():
            execution = await session.get(
                NetworkExecutionModel,
                execution_id,
                with_for_update=True,
            )
            if execution is None or execution.project_id != project_id:
                raise NotFoundError("Network execution not found")
            if execution.status not in {"queued", "running"}:
                return
            now = datetime.now(timezone.utc)
            execution.cancel_requested_at = now
            if execution.status == "queued":
                execution.status = "cancelled"
                execution.completed_at = now
                execution.last_event_sequence += 1
                session.add(
                    NetworkExecutionEventModel(
                        network_execution_id=execution.id,
                        network_session_id=execution.network_session_id,
                        sequence=execution.last_event_sequence,
                        event_type="execution_cancelled",
                        payload={"cancelled_before_start": True},
                    )
                )
            else:
                execution.status = "cancel_requested"
