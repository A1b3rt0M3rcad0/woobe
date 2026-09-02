from modules.network.application.dtos.compatibility import (
    EnsureProjectNetworkInput,
    GetLegacyProjectNetworkInput,
)
from modules.network.application.dtos.resources import NetworkResourceOutput
from modules.network.application.interfaces.project_lookup import ProjectLookup
from modules.network.application.interfaces.resource_repository import (
    NetworkResourceRepository,
)
from modules.network.domain.entities import Network
from shared.contracts.errors import ConflictError, NotFoundError


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


def _single_network(networks: list[Network]) -> Network | None:
    if len(networks) > 1:
        raise ConflictError(
            "Multiple Networks exist in this Project; select a Network explicitly"
        )
    return networks[0] if networks else None


class EnsureProjectNetworkUseCase:
    def __init__(
        self,
        repository: NetworkResourceRepository,
        project_lookup: ProjectLookup,
    ) -> None:
        self._repository = repository
        self._project_lookup = project_lookup

    async def execute(
        self,
        input_dto: EnsureProjectNetworkInput,
    ) -> NetworkResourceOutput:
        if not await self._project_lookup.exists(input_dto.project_id):
            raise NotFoundError("Project not found")

        existing = _single_network(
            await self._repository.list_by_project(input_dto.project_id)
        )
        if existing is not None:
            return _output(existing)

        name = input_dto.name.strip() or "Project Network"
        try:
            created = await self._repository.create(
                project_id=input_dto.project_id,
                name=name,
                description="",
            )
            return _output(created)
        except ConflictError:
            raced = _single_network(
                await self._repository.list_by_project(input_dto.project_id)
            )
            if raced is None:
                raise
            return _output(raced)


class GetLegacyProjectNetworkUseCase:
    def __init__(self, repository: NetworkResourceRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: GetLegacyProjectNetworkInput,
    ) -> NetworkResourceOutput:
        network = _single_network(
            await self._repository.list_by_project(input_dto.project_id)
        )
        if network is None:
            raise NotFoundError("Network not found")
        return _output(network)
