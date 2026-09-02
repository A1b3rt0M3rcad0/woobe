from typing import Any

from modules.network.application.dtos.execution import (
    AcceptNetworkExecutionInput,
    AcceptedNetworkExecution,
    PersistNetworkExecutionInput,
)
from modules.network.application.interfaces.agent_runtime_binding import (
    AgentRuntimeBindingGateway,
)
from modules.network.application.interfaces.execution_repository import (
    NetworkExecutionAcceptanceRepository,
)
from modules.network.application.interfaces.session_repository import (
    NetworkRuntimeEnvironmentRepository,
)
from modules.network.domain.entities import NetworkDefinition
from modules.network.domain.enums import NetworkEnvironment
from modules.network.domain.graph import composition_hash, validate_network_definition
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError


class AcceptNetworkExecutionUseCase:
    def __init__(
        self,
        repository: NetworkExecutionAcceptanceRepository,
        agent_gateway: AgentRuntimeBindingGateway,
        environment_repository: NetworkRuntimeEnvironmentRepository,
        *,
        hard_max_depth: int,
        hard_max_invocations: int,
        hard_timeout_seconds: int,
    ) -> None:
        self._repository = repository
        self._agent_gateway = agent_gateway
        self._environment_repository = environment_repository
        self._hard_max_depth = hard_max_depth
        self._hard_max_invocations = hard_max_invocations
        self._hard_timeout_seconds = hard_timeout_seconds

    async def execute(
        self,
        input_dto: AcceptNetworkExecutionInput,
    ) -> AcceptedNetworkExecution:
        message = input_dto.message.strip()
        if not message:
            raise ValidationError("Network message cannot be blank")

        if input_dto.idempotency_key:
            existing = await self._repository.find_idempotent(
                network_id=input_dto.network_id,
                idempotency_key=input_dto.idempotency_key,
            )
            if existing is not None:
                if existing.project_id != input_dto.project_id:
                    raise NotFoundError("Network execution not found")
                if input_dto.expected_environment is not None:
                    existing_session = await self._repository.get_session(
                        network_id=input_dto.network_id,
                        project_id=input_dto.project_id,
                        network_session_id=existing.network_session_id,
                        lock=False,
                    )
                    if (
                        existing_session is None
                        or existing_session.environment != input_dto.expected_environment
                    ):
                        raise NotFoundError("Network execution not found")
                return existing

        network_session = await self._repository.get_session(
            network_id=input_dto.network_id,
            project_id=input_dto.project_id,
            network_session_id=input_dto.network_session_id,
            lock=True,
        )
        if network_session is None or network_session.status != "active":
            raise NotFoundError("Network Session not found")
        if (
            input_dto.expected_environment is not None
            and network_session.environment != input_dto.expected_environment
        ):
            raise NotFoundError("Network Session not found")

        await self._environment_repository.require_enabled(
            network_id=input_dto.network_id,
            project_id=input_dto.project_id,
            environment=network_session.environment,
        )

        active = await self._repository.find_active(input_dto.network_session_id)
        if active is not None:
            raise ConflictError(
                f"Network Session already has an active execution: {active.id}"
            )

        accepted_version_id = network_session.network_version_id
        accepted_version: str | None = None
        draft_revision: int | None = None
        definition_snapshot: dict[str, Any] | None = None
        bindings_snapshot: dict[str, Any] | None = None

        if network_session.environment == NetworkEnvironment.DRAFT.value:
            network = await self._repository.get_network(
                network_id=input_dto.network_id,
                project_id=input_dto.project_id,
                lock=True,
            )
            if network is None:
                raise NotFoundError("Network not found")
            if (
                input_dto.expected_draft_revision is not None
                and input_dto.expected_draft_revision != network.draft_revision
            ):
                raise ConflictError(
                    "Network Draft changed before the execution was accepted"
                )
            definition = self._definition(network.draft_definition)
            try:
                bindings_snapshot = await self._agent_gateway.resolve_runtime_bindings(
                    project_id=input_dto.project_id,
                    nodes=[
                        {
                            "node_id": node.id,
                            "agent_id": node.agent_id,
                            "binding_source": node.binding.source,
                            "release_id": node.binding.release_id,
                        }
                        for node in definition.nodes
                    ],
                )
            except ValueError as exc:
                raise ConflictError(str(exc)) from exc
            draft_revision = network.draft_revision
            definition_snapshot = definition.to_dict()
            accepted_composition_hash = composition_hash(
                definition,
                bindings_snapshot,
            )
        else:
            if accepted_version_id is None:
                raise ConflictError("Pinned Network version was not found")
            version = await self._repository.get_version(
                version_id=accepted_version_id,
                network_id=input_dto.network_id,
                project_id=input_dto.project_id,
            )
            if version is None:
                raise ConflictError("Pinned Network version was not found")
            definition = self._definition(version.definition)
            accepted_version = version.version
            accepted_composition_hash = version.composition_hash

        return await self._repository.persist_acceptance(
            PersistNetworkExecutionInput(
                project_id=input_dto.project_id,
                network_id=input_dto.network_id,
                network_session_id=input_dto.network_session_id,
                network_version_id=accepted_version_id,
                message=message,
                idempotency_key=input_dto.idempotency_key,
                environment=network_session.environment,
                origin=network_session.origin,
                chat_surface_id=network_session.chat_surface_id,
                draft_revision=draft_revision,
                definition_snapshot=definition_snapshot,
                resolved_bindings_snapshot=bindings_snapshot,
                accepted_version=accepted_version,
                accepted_composition_hash=accepted_composition_hash,
                root_node_id=definition.root_node_id,
                limits={
                    "max_depth": definition.limits.max_depth,
                    "max_invocations": definition.limits.max_invocations,
                    "timeout_seconds": definition.limits.timeout_seconds,
                },
            )
        )

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
