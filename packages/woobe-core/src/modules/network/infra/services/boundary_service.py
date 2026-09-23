from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from modules.core.infra.database.models import ProjectModel
from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkModel,
    NetworkSessionModel,
    NetworkVersionModel,
)
from modules.network.infra.database.repositories import NetworkRuntimeRepository
from modules.network.infra.database.run_diagnostics_reader import (
    NetworkRunDiagnosticsReader,
)
from modules.network.infra.database.schema_extensions import (
    NetworkProductionActivationModel,
    version_extension_payload,
)
from modules.network.infra.services.service import NetworkApplicationService
from shared.infra.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from shared.contracts.runtime_contracts import (
    RuntimeContractSnapshot,
    effective_external_context_contract_schema,
    normalize_contract_schema,
)
from shared.runtime_environment import assert_runtime_environment_enabled
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal
from shared.security.tenancy import TenantAuthorizer


_ACTIVE_STATUSES = {"queued", "running", "cancel_requested"}


class NetworkBoundaryService(NetworkApplicationService):
    """Transport-neutral Network capability used by synchronous process hosts.

    Database queries that previously leaked into FastAPI routers live here so
    the HTTP host only authenticates, validates transport input and serializes
    the returned module data.
    """

    async def list_project_networks(self, project_id: UUID) -> list[NetworkModel]:
        async with self._session_factory() as session:
            project_exists = await session.scalar(
                select(ProjectModel.id).where(ProjectModel.id == project_id)
            )
            if project_exists is None:
                raise NotFoundError("Project not found")
            return list(
                (
                    await session.scalars(
                        select(NetworkModel)
                        .where(NetworkModel.project_id == project_id)
                        .order_by(
                            NetworkModel.updated_at.desc(),
                            NetworkModel.created_at.desc(),
                        )
                    )
                ).all()
            )

    async def create_project_network(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str,
    ) -> NetworkModel:
        async with self._session_factory() as session, session.begin():
            project_exists = await session.scalar(
                select(ProjectModel.id).where(ProjectModel.id == project_id)
            )
            if project_exists is None:
                raise NotFoundError("Project not found")
            duplicate = await session.scalar(
                select(NetworkModel.id).where(
                    NetworkModel.project_id == project_id,
                    func.lower(func.btrim(NetworkModel.name)) == name.lower(),
                )
            )
            if duplicate is not None:
                raise ConflictError(
                    "A Network with this name already exists in the Project"
                )
            network = NetworkModel(
                project_id=project_id,
                name=name,
                description=description,
                draft_definition={},
                draft_revision=0,
                staging_version_id=None,
                production_version_id=None,
            )
            session.add(network)
            try:
                await session.flush()
            except IntegrityError as exc:
                raise ConflictError(
                    "A Network with this name already exists in the Project"
                ) from exc
            return network

    async def get_project_network(
        self,
        *,
        project_id: UUID,
        network_id: UUID,
    ) -> NetworkModel:
        async with self._session_factory() as session:
            network = await session.scalar(
                select(NetworkModel).where(
                    NetworkModel.id == network_id,
                    NetworkModel.project_id == project_id,
                )
            )
            if network is None:
                raise NotFoundError("Network not found")
            return network

    async def update_project_network_metadata(
        self,
        *,
        project_id: UUID,
        network_id: UUID,
        name: str | None,
        description: str | None,
    ) -> NetworkModel:
        async with self._session_factory() as session, session.begin():
            network = await session.scalar(
                select(NetworkModel)
                .where(
                    NetworkModel.id == network_id,
                    NetworkModel.project_id == project_id,
                )
                .with_for_update()
            )
            if network is None:
                raise NotFoundError("Network not found")
            if name is not None:
                duplicate = await session.scalar(
                    select(NetworkModel.id).where(
                        NetworkModel.project_id == project_id,
                        NetworkModel.id != network_id,
                        func.lower(func.btrim(NetworkModel.name)) == name.lower(),
                    )
                )
                if duplicate is not None:
                    raise ConflictError(
                        "A Network with this name already exists in the Project"
                    )
                network.name = name
            if description is not None:
                network.description = description
            try:
                await session.flush()
            except IntegrityError as exc:
                raise ConflictError(
                    "A Network with this name already exists in the Project"
                ) from exc
            return network

    async def delete_project_network(
        self,
        *,
        project_id: UUID,
        network_id: UUID,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            network = await session.scalar(
                select(NetworkModel)
                .where(
                    NetworkModel.id == network_id,
                    NetworkModel.project_id == project_id,
                )
                .with_for_update()
            )
            if network is None:
                raise NotFoundError("Network not found")

            version_id = await session.scalar(
                select(NetworkVersionModel.id)
                .where(NetworkVersionModel.network_id == network_id)
                .limit(1)
            )
            session_id = await session.scalar(
                select(NetworkSessionModel.id)
                .where(NetworkSessionModel.network_id == network_id)
                .limit(1)
            )
            activation_id = await session.scalar(
                select(NetworkProductionActivationModel.id)
                .where(NetworkProductionActivationModel.network_id == network_id)
                .limit(1)
            )
            if version_id is not None or session_id is not None or activation_id is not None:
                raise ConflictError(
                    "Network has version or runtime history and cannot be deleted"
                )

            await session.delete(network)
            await session.flush()

    async def list_managed_versions(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
    ) -> list[NetworkVersionModel]:
        async with self._session_factory() as session:
            await self._require_network(session, network_id, project_id)
            return list(
                (
                    await session.scalars(
                        select(NetworkVersionModel)
                        .where(
                            NetworkVersionModel.network_id == network_id,
                            NetworkVersionModel.project_id == project_id,
                        )
                        .order_by(NetworkVersionModel.created_at.desc())
                    )
                ).all()
            )

    async def list_production_activations(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
    ) -> list[NetworkProductionActivationModel]:
        async with self._session_factory() as session:
            await self._require_network(session, network_id, project_id)
            return list(
                (
                    await session.scalars(
                        select(NetworkProductionActivationModel)
                        .where(
                            NetworkProductionActivationModel.network_id == network_id,
                            NetworkProductionActivationModel.project_id == project_id,
                        )
                        .order_by(NetworkProductionActivationModel.created_at.desc())
                    )
                ).all()
            )

    async def execution_snapshot(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            if execution is None or execution.project_id != project_id:
                raise NotFoundError("Network execution not found")
            network_session = await session.get(
                NetworkSessionModel,
                execution.network_session_id,
            )
            if network_session is None or network_session.project_id != project_id:
                raise NotFoundError("Network Session not found")

            snapshot_source = "execution"
            definition = execution.definition_snapshot
            bindings = execution.resolved_bindings_snapshot
            version_label = (
                f"Draft r{execution.draft_revision}"
                if execution.draft_revision is not None
                else None
            )
            if execution.network_version_id is not None:
                version = await session.get(
                    NetworkVersionModel,
                    execution.network_version_id,
                )
                if (
                    version is None
                    or version.project_id != project_id
                    or version.network_id != execution.network_id
                ):
                    raise NotFoundError("Network execution version not found")
                snapshot_source = "network_version"
                definition = version.definition
                bindings = version.resolved_bindings
                version_label = version.version

            if not definition or bindings is None:
                raise NotFoundError("Exact Network execution snapshot is unavailable")

            events = list(
                (
                    await session.scalars(
                        select(NetworkExecutionEventModel)
                        .where(
                            NetworkExecutionEventModel.network_execution_id
                            == execution.id
                        )
                        .order_by(NetworkExecutionEventModel.sequence)
                    )
                ).all()
            )
            accepted = next(
                (item for item in events if item.event_type == "execution_accepted"),
                None,
            )
            composition_hash = (
                str((accepted.payload or {}).get("composition_hash"))
                if accepted and (accepted.payload or {}).get("composition_hash")
                else None
            )

            session_contexts = list(
                (
                    await session.scalars(
                        select(NetworkAgentContextModel).where(
                            NetworkAgentContextModel.network_session_id
                            == execution.network_session_id
                        )
                    )
                ).all()
            )
            contexts_by_node = {
                str(item.network_node_id): {
                    "node_id": str(item.network_node_id),
                    "agent_id": str(item.agent_id),
                    "agent_session_id": (
                        str(item.agent_session_id)
                        if item.agent_session_id
                        else None
                    ),
                }
                for item in session_contexts
            }
            for event in events:
                if event.node_id is None or event.agent_id is None:
                    continue
                data = event.payload or {}
                node_id = str(event.node_id)
                context = contexts_by_node.setdefault(
                    node_id,
                    {
                        "node_id": node_id,
                        "agent_id": str(event.agent_id),
                        "agent_session_id": None,
                    },
                )
                for key in ("agent_session_id", "source", "version", "provider", "model"):
                    if data.get(key):
                        context[key] = str(data[key])

            return {
                "execution_id": str(execution.id),
                "network_id": str(execution.network_id),
                "network_session_id": str(execution.network_session_id),
                "environment": network_session.environment,
                "draft_revision": execution.draft_revision,
                "network_version_id": (
                    str(execution.network_version_id)
                    if execution.network_version_id
                    else None
                ),
                "version_label": version_label,
                "composition_hash": composition_hash,
                "definition": definition,
                "resolved_bindings": bindings,
                "snapshot_source": snapshot_source,
                "agent_contexts": list(contexts_by_node.values()),
                "parsed_output": execution.parsed_output,
                "output_parse_error": execution.output_parse_error,
            }

    async def activate_production(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        source_version_id: UUID,
        expected_current_production_version_id: UUID | None,
        change_description: str,
        created_by: UUID | None,
    ) -> tuple[NetworkVersionModel, NetworkProductionActivationModel]:
        async with self._session_factory() as session, session.begin():
            network = await session.get(NetworkModel, network_id, with_for_update=True)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network not found")
            if expected_current_production_version_id != network.production_version_id:
                raise ConflictError(
                    "Production changed after this release was selected. "
                    "Review the current Production release again."
                )
            source = await session.get(NetworkVersionModel, source_version_id)
            if (
                source is None
                or source.network_id != network.id
                or source.project_id != project_id
                or source.kind != "release"
            ):
                raise NotFoundError("Historical Network Release not found")
            if source.id == network.production_version_id:
                raise ConflictError(
                    "Selected Network Release is already in Production"
                )
            previous = (
                await session.get(NetworkVersionModel, network.production_version_id)
                if network.production_version_id
                else None
            )
            activation_kind = (
                "rollback"
                if previous is not None and source.created_at < previous.created_at
                else "reactivate"
            )
            activation = NetworkProductionActivationModel(
                network_id=network.id,
                project_id=project_id,
                version_id=source.id,
                previous_version_id=network.production_version_id,
                activation_kind=activation_kind,
                change_description=change_description,
                created_by=created_by,
            )
            session.add(activation)
            network.production_version_id = source.id
            await session.flush()
            return source, activation

    async def execution_with_session(
        self,
        execution_id: UUID,
    ) -> tuple[NetworkExecutionModel, NetworkSessionModel | None]:
        async with self._session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            if execution is None:
                raise NotFoundError("Network execution not found")
            network_session = await session.get(
                NetworkSessionModel,
                execution.network_session_id,
            )
            return execution, network_session

    async def authorized_execution(
        self,
        *,
        execution_id: UUID,
        principal: AuthenticatedPrincipal | ProjectApiPrincipal | None,
    ) -> NetworkExecutionModel:
        async with self._session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            if execution is None:
                raise NotFoundError("Network execution not found")
            network_session = await session.get(
                NetworkSessionModel,
                execution.network_session_id,
            )
            await self._authorize_execution(
                session,
                execution,
                network_session,
                principal,
            )
            return execution

    async def active_execution(
        self,
        *,
        principal: AuthenticatedPrincipal | ProjectApiPrincipal | None,
        network_session_id: UUID | None,
        network_id: UUID | None,
        environment: str | None,
    ) -> NetworkExecutionModel | None:
        async with self._session_factory() as session:
            statement = (
                select(NetworkExecutionModel)
                .join(
                    NetworkSessionModel,
                    NetworkSessionModel.id
                    == NetworkExecutionModel.network_session_id,
                )
                .where(NetworkExecutionModel.status.in_(_ACTIVE_STATUSES))
            )
            if network_session_id is not None:
                statement = statement.where(
                    NetworkExecutionModel.network_session_id == network_session_id
                )
            if network_id is not None:
                statement = statement.where(
                    NetworkExecutionModel.network_id == network_id
                )
            if environment is not None:
                statement = statement.where(
                    NetworkSessionModel.environment == environment
                )
            execution = await session.scalar(
                statement.order_by(
                    NetworkExecutionModel.created_at.desc(),
                    NetworkExecutionModel.id.desc(),
                ).limit(1)
            )
            if execution is None:
                return None
            network_session = await session.get(
                NetworkSessionModel,
                execution.network_session_id,
            )
            await self._authorize_execution(
                session,
                execution,
                network_session,
                principal,
            )
            return execution

    async def get_session(
        self,
        session_id: UUID,
    ) -> NetworkSessionModel | None:
        async with self._session_factory() as session:
            return await session.get(NetworkSessionModel, session_id)

    async def idempotent_execution(
        self,
        *,
        network_id: UUID,
        idempotency_key: str | None,
    ) -> tuple[NetworkExecutionModel, NetworkSessionModel] | None:
        if not idempotency_key:
            return None
        async with self._session_factory() as session:
            execution = await session.scalar(
                select(NetworkExecutionModel).where(
                    NetworkExecutionModel.network_id == network_id,
                    NetworkExecutionModel.idempotency_key == idempotency_key,
                )
            )
            if execution is None:
                return None
            network_session = await session.get(
                NetworkSessionModel,
                execution.network_session_id,
            )
            if network_session is None:
                return None
            return execution, network_session

    async def list_sessions(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
    ) -> list[tuple[NetworkSessionModel, int, int]]:
        async with self._session_factory() as session:
            message_count = (
                select(func.count(NetworkMessageModel.id))
                .where(
                    NetworkMessageModel.network_session_id == NetworkSessionModel.id
                )
                .correlate(NetworkSessionModel)
                .scalar_subquery()
            )
            execution_count = (
                select(func.count(NetworkExecutionModel.id))
                .where(
                    NetworkExecutionModel.network_session_id == NetworkSessionModel.id
                )
                .correlate(NetworkSessionModel)
                .scalar_subquery()
            )
            result = await session.execute(
                select(
                    NetworkSessionModel,
                    message_count.label("message_count"),
                    execution_count.label("trace_count"),
                )
                .where(
                    NetworkSessionModel.network_id == network_id,
                    NetworkSessionModel.project_id == project_id,
                )
                .order_by(NetworkSessionModel.created_at.desc())
                .limit(100)
            )
            return [
                (item, int(messages or 0), int(traces or 0))
                for item, messages, traces in result.all()
            ]

    async def list_session_messages(
        self,
        *,
        network_id: UUID,
        network_session_id: UUID,
        project_id: UUID,
        offset: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            network_session = await session.get(
                NetworkSessionModel,
                network_session_id,
            )
            if (
                network_session is None
                or network_session.network_id != network_id
                or network_session.project_id != project_id
            ):
                raise NotFoundError("Network Session not found")
            result = await session.execute(
                select(NetworkMessageModel, NetworkExecutionModel)
                .outerjoin(
                    NetworkExecutionModel,
                    NetworkExecutionModel.id
                    == NetworkMessageModel.network_execution_id,
                )
                .where(
                    NetworkMessageModel.network_session_id == network_session_id,
                    NetworkMessageModel.project_id == project_id,
                )
                .order_by(NetworkMessageModel.created_at.asc())
                .offset(offset)
                .limit(limit)
            )
            rows = list(result.all())
            execution_ids = {
                execution.id for _, execution in rows if execution is not None
            }
            events_by_execution: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
            if execution_ids:
                event_result = await session.execute(
                    select(NetworkExecutionEventModel)
                    .where(
                        NetworkExecutionEventModel.network_execution_id.in_(
                            execution_ids
                        )
                    )
                    .order_by(
                        NetworkExecutionEventModel.network_execution_id,
                        NetworkExecutionEventModel.sequence,
                    )
                )
                for event in event_result.scalars():
                    events_by_execution[event.network_execution_id].append(
                        self._event_payload(event, data_key="data")
                    )
            return [
                self._message_payload(message, execution, events_by_execution)
                for message, execution in rows
            ]

    async def reset_session_context(
        self,
        *,
        network_id: UUID,
        network_session_id: UUID,
        project_id: UUID,
    ) -> None:
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
            ):
                raise NotFoundError("Network Session not found")
            active = await session.scalar(
                select(NetworkExecutionModel.id).where(
                    NetworkExecutionModel.network_session_id == network_session_id,
                    NetworkExecutionModel.status.in_(_ACTIVE_STATUSES),
                )
            )
            if active is not None:
                raise ConflictError(
                    "Wait for the active execution before resetting context"
                )
            await session.execute(
                delete(NetworkAgentContextModel).where(
                    NetworkAgentContextModel.network_session_id
                    == network_session_id
                )
            )

    async def get_execution(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
    ) -> NetworkExecutionModel:
        async with self._session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            if execution is None or execution.project_id != project_id:
                raise NotFoundError("Network execution not found")
            return execution

    async def get_public_execution(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
        network_id: UUID | None,
        environment: str | None,
    ) -> tuple[NetworkExecutionModel, NetworkSessionModel]:
        execution, network_session = await self.execution_with_session(execution_id)
        if (
            network_session is None
            or execution.project_id != project_id
            or execution.network_id != network_id
            or network_session.environment != environment
        ):
            raise NotFoundError("Network job not found")
        return execution, network_session

    async def list_execution_events(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
        after_sequence: int,
    ) -> list[NetworkExecutionEventModel]:
        async with self._session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            if execution is None or execution.project_id != project_id:
                raise NotFoundError("Network execution not found")
            return await NetworkRuntimeRepository(session).list_events_after(
                execution_id,
                after_sequence,
            )

    async def diagnostics(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
    ) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            return await NetworkRunDiagnosticsReader(session).get(
                execution_id,
                project_id,
            )

    async def runtime_contract_snapshot(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: str,
    ) -> RuntimeContractSnapshot:
        if environment not in {"staging", "production"}:
            raise ConflictError("Runtime Key binding is incomplete")

        async with self._session_factory() as session:
            network = await self._require_network(session, network_id, project_id)
            version_id = (
                network.staging_version_id
                if environment == "staging"
                else network.production_version_id
            )
            if version_id is None:
                raise NotFoundError(f"Network {environment} Release not found")

            version = await session.get(NetworkVersionModel, version_id)
            if (
                version is None
                or version.network_id != network_id
                or version.project_id != project_id
            ):
                raise NotFoundError("Network Release not found")

            public_output_contract = getattr(version, "public_output_contract", None)
            output_contract = None
            if isinstance(public_output_contract, dict) and public_output_contract.get(
                "enabled", True
            ):
                schema = public_output_contract.get("schema")
                json_schema = public_output_contract.get("json_schema")
                if schema is None and isinstance(json_schema, dict):
                    schema = json_schema.get("schema")
                output_contract = normalize_contract_schema(schema)

            return RuntimeContractSnapshot(
                release_id=str(version.id),
                release_version=str(version.version),
                output_contract=output_contract,
                external_context=effective_external_context_contract_schema(
                    getattr(version, "effective_external_context_contract", None)
                ),
            )

    async def assert_runtime_environment(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: str,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await assert_runtime_environment_enabled(
                session,
                target_type="network",
                target_id=network_id,
                project_id=project_id,
                environment=environment,
            )

    @staticmethod
    def version_extension_payload(version) -> dict[str, Any]:
        return version_extension_payload(version)

    @staticmethod
    async def _require_network(session, network_id: UUID, project_id: UUID):
        network = await session.get(NetworkModel, network_id)
        if network is None or network.project_id != project_id:
            raise NotFoundError("Network not found")
        return network

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

    async def _authorize_execution(
        self,
        session,
        execution: NetworkExecutionModel,
        network_session: NetworkSessionModel | None,
        principal: AuthenticatedPrincipal | ProjectApiPrincipal | None,
    ) -> None:
        if isinstance(principal, ProjectApiPrincipal):
            if principal.project_id != execution.project_id:
                raise AuthorizationError(
                    "Runtime key does not belong to this Project"
                )
            if principal.kind == "runtime":
                target_type, target_id = self._runtime_target(principal)
                if target_type != "network" or target_id != execution.network_id:
                    raise NotFoundError("Network execution not found")
                if (
                    principal.environment is not None
                    and (
                        network_session is None
                        or principal.environment != network_session.environment
                    )
                ):
                    raise NotFoundError("Network execution not found")
            return
        if isinstance(principal, AuthenticatedPrincipal):
            await TenantAuthorizer(session).authorize(
                user_id=principal.user_id,
                path_params={},
                query_params={"project_id": execution.project_id},
                body=None,
            )
            return
        raise AuthorizationError("Authentication required")

    @staticmethod
    def _event_payload(event, *, data_key: str) -> dict[str, Any]:
        return {
            "id": str(event.id),
            "sequence": event.sequence,
            "event_type": event.event_type,
            "invocation_id": (
                str(event.invocation_id) if event.invocation_id else None
            ),
            "parent_invocation_id": (
                str(event.parent_invocation_id)
                if event.parent_invocation_id
                else None
            ),
            "node_id": str(event.node_id) if event.node_id else None,
            "agent_id": str(event.agent_id) if event.agent_id else None,
            "depth": event.depth,
            data_key: event.payload,
            "created_at": event.created_at,
        }

    def _message_payload(
        self,
        message,
        execution,
        events_by_execution: dict[UUID, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        execution_events = (
            events_by_execution[execution.id] if execution is not None else []
        )
        return {
            "id": str(message.id),
            "network_execution_id": (
                str(message.network_execution_id)
                if message.network_execution_id
                else None
            ),
            "role": message.role,
            "content": message.content,
            "data": message.data,
            "created_at": message.created_at,
            "execution": (
                {
                    "id": str(execution.id),
                    "status": execution.status,
                    "draft_revision": execution.draft_revision,
                    "network_version_id": (
                        str(execution.network_version_id)
                        if execution.network_version_id
                        else None
                    ),
                    "root_trace_id": (
                        str(execution.root_trace_id)
                        if execution.root_trace_id
                        else None
                    ),
                    "failure_code": execution.failure_code,
                    "failure": next(
                        (
                            event["data"]
                            for event in reversed(execution_events)
                            if event["event_type"] == "execution_failed"
                        ),
                        None,
                    ),
                    "started_at": execution.started_at,
                    "completed_at": execution.completed_at,
                    "events": execution_events,
                }
                if execution is not None
                else None
            ),
        }


__all__ = ["NetworkBoundaryService"]
