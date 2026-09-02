from modules.network.application.dtos.resources import (
    CreateProjectNetworkInput,
    GetProjectNetworkInput,
    ListProjectNetworksInput,
    NetworkResourceOutput,
    UpdateProjectNetworkInput,
)
from modules.network.application.interfaces.project_lookup import ProjectLookup
from modules.network.application.interfaces.resource_repository import (
    NetworkResourceRepository,
)
from modules.network.domain.entities import Network
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


class ListProjectNetworksUseCase:
    def __init__(
        self,
        repository: NetworkResourceRepository,
        project_lookup: ProjectLookup,
    ) -> None:
        self._repository = repository
        self._project_lookup = project_lookup

    async def execute(
        self,
        input_dto: ListProjectNetworksInput,
    ) -> list[NetworkResourceOutput]:
        if not await self._project_lookup.exists(input_dto.project_id):
            raise NotFoundError("Project not found")
        return [
            _output(network)
            for network in await self._repository.list_by_project(input_dto.project_id)
        ]


class CreateProjectNetworkUseCase:
    def __init__(
        self,
        repository: NetworkResourceRepository,
        project_lookup: ProjectLookup,
    ) -> None:
        self._repository = repository
        self._project_lookup = project_lookup

    async def execute(
        self,
        input_dto: CreateProjectNetworkInput,
    ) -> NetworkResourceOutput:
        if not await self._project_lookup.exists(input_dto.project_id):
            raise NotFoundError("Project not found")
        name = input_dto.name.strip()
        description = input_dto.description.strip()
        if not name:
            raise ValidationError("Network name cannot be blank")
        if await self._repository.name_exists(input_dto.project_id, name):
            raise ConflictError("A Network with this name already exists in the Project")
        network = await self._repository.create(
            project_id=input_dto.project_id,
            name=name,
            description=description,
        )
        return _output(network)


class GetProjectNetworkUseCase:
    def __init__(self, repository: NetworkResourceRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: GetProjectNetworkInput,
    ) -> NetworkResourceOutput:
        network = await self._repository.get_for_project(
            input_dto.project_id,
            input_dto.network_id,
        )
        if network is None:
            raise NotFoundError("Network not found")
        return _output(network)


class UpdateProjectNetworkUseCase:
    def __init__(self, repository: NetworkResourceRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: UpdateProjectNetworkInput,
    ) -> NetworkResourceOutput:
        if input_dto.name is None and input_dto.description is None:
            raise ValidationError("At least one Network metadata field is required")

        name = input_dto.name.strip() if input_dto.name is not None else None
        description = (
            input_dto.description.strip()
            if input_dto.description is not None
            else None
        )
        if name is not None and not name:
            raise ValidationError("Network name cannot be blank")
        if name is not None and await self._repository.name_exists(
            input_dto.project_id,
            name,
            exclude_network_id=input_dto.network_id,
        ):
            raise ConflictError("A Network with this name already exists in the Project")

        network = await self._repository.update_metadata(
            project_id=input_dto.project_id,
            network_id=input_dto.network_id,
            name=name,
            description=description,
        )
        if network is None:
            raise NotFoundError("Network not found")
        return _output(network)
