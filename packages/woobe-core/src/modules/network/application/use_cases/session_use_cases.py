from modules.network.application.dtos.sessions import (
    CreateNetworkSessionInput,
    NetworkSessionOutput,
)
from modules.network.application.interfaces.resource_repository import (
    NetworkResourceRepository,
)
from modules.network.application.interfaces.session_repository import (
    NetworkRuntimeEnvironmentRepository,
    NetworkSessionRepository,
)
from modules.network.domain.entities import NetworkDefinition, NetworkSession
from modules.network.domain.enums import NetworkEnvironment, NetworkSessionStatus
from modules.network.domain.graph import validate_network_definition
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError


class CreateNetworkSessionUseCase:
    def __init__(
        self,
        network_repository: NetworkResourceRepository,
        session_repository: NetworkSessionRepository,
        environment_repository: NetworkRuntimeEnvironmentRepository,
        *,
        hard_max_depth: int,
        hard_max_invocations: int,
        hard_timeout_seconds: int,
    ) -> None:
        self._network_repository = network_repository
        self._session_repository = session_repository
        self._environment_repository = environment_repository
        self._hard_max_depth = hard_max_depth
        self._hard_max_invocations = hard_max_invocations
        self._hard_timeout_seconds = hard_timeout_seconds

    async def execute(
        self,
        input_dto: CreateNetworkSessionInput,
    ) -> NetworkSessionOutput:
        network = await self._network_repository.get_for_project(
            input_dto.project_id,
            input_dto.network_id,
        )
        if network is None:
            raise NotFoundError("Network not found")

        await self._environment_repository.require_enabled(
            network_id=input_dto.network_id,
            project_id=input_dto.project_id,
            environment=input_dto.environment.value,
        )

        if input_dto.environment == NetworkEnvironment.DRAFT:
            self._validate_definition(network.draft_definition)
            version_id = None
        else:
            version_id = (
                network.staging_version_id
                if input_dto.environment == NetworkEnvironment.STAGING
                else network.production_version_id
            )
            if version_id is None:
                raise ConflictError(
                    f"Network {input_dto.environment.value} is not ready"
                )

        title = input_dto.title.strip() or "New Network session"
        session = await self._session_repository.create(
            NetworkSession(
                network_id=network.id,
                network_version_id=version_id,
                project_id=input_dto.project_id,
                environment=input_dto.environment,
                title=title,
                tenant_id=input_dto.tenant_id,
                user_id=input_dto.user_id,
                external_session_id=input_dto.external_session_id,
                status=NetworkSessionStatus.ACTIVE,
            )
        )
        return NetworkSessionOutput(
            id=session.id,
            network_id=session.network_id,
            network_version_id=session.network_version_id,
            environment=session.environment.value,
            title=session.title,
            status=session.status.value,
            last_message_at=None,
            message_count=0,
            trace_count=0,
            created_at=session.created_at,
        )

    def _validate_definition(self, raw_definition: dict) -> None:
        try:
            definition = NetworkDefinition.from_dict(raw_definition)
            validate_network_definition(
                definition,
                hard_max_depth=self._hard_max_depth,
                hard_max_invocations=self._hard_max_invocations,
                hard_timeout_seconds=self._hard_timeout_seconds,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(str(exc)) from exc
