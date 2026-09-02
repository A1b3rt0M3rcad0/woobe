from modules.network.application.dtos.draft import SaveNetworkDraftInput
from modules.network.application.dtos.resources import NetworkResourceOutput
from modules.network.application.interfaces.agent_availability import AgentAvailability
from modules.network.application.interfaces.draft_repository import (
    NetworkDraftRepository,
)
from modules.network.domain.entities import Network, NetworkDefinition
from modules.network.domain.graph import validate_network_definition
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError


def _output(network: Network) -> NetworkResourceOutput:
    definition = network.draft_definition or {}
    nodes = definition.get("nodes") if isinstance(definition, dict) else None
    return NetworkResourceOutput(
        id=network.id,
        project_id=network.project_id,
        name=network.name,
        description=network.description,
        draft_definition=definition,
        draft_revision=network.draft_revision,
        staging_version_id=network.staging_version_id,
        production_version_id=network.production_version_id,
        agent_count=len(nodes) if isinstance(nodes, list) else 0,
        created_at=network.created_at,
        updated_at=network.updated_at,
    )


class SaveNetworkDraftUseCase:
    def __init__(
        self,
        repository: NetworkDraftRepository,
        agent_availability: AgentAvailability,
        *,
        hard_max_depth: int,
        hard_max_invocations: int,
        hard_timeout_seconds: int,
    ) -> None:
        self._repository = repository
        self._agent_availability = agent_availability
        self._hard_max_depth = hard_max_depth
        self._hard_max_invocations = hard_max_invocations
        self._hard_timeout_seconds = hard_timeout_seconds

    async def execute(self, input_dto: SaveNetworkDraftInput) -> NetworkResourceOutput:
        network = await self._repository.get_for_project(
            network_id=input_dto.network_id,
            project_id=input_dto.project_id,
        )
        if network is None:
            raise NotFoundError("Network not found")

        definition = self._definition(input_dto.definition)
        agent_ids = [node.agent_id for node in definition.nodes]
        if len(agent_ids) != len(set(agent_ids)):
            raise ConflictError(
                "The same Agent cannot appear more than once in a Network Draft"
            )

        unavailable = await self._agent_availability.unavailable_active_agent_ids(
            project_id=input_dto.project_id,
            agent_ids=set(agent_ids),
        )
        if unavailable:
            joined = ", ".join(sorted(str(agent_id) for agent_id in unavailable))
            raise ConflictError(
                f"Network Draft references inactive or unavailable Agents: {joined}"
            )

        saved = await self._repository.save_draft(
            network_id=input_dto.network_id,
            project_id=input_dto.project_id,
            expected_revision=input_dto.expected_revision,
            definition=definition.to_dict(),
        )
        if saved is None:
            raise ConflictError("Network Draft was changed by another request")
        return _output(saved)

    def _definition(self, value: dict) -> NetworkDefinition:
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
