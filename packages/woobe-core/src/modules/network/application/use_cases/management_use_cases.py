from modules.network.application.dtos.management import (
    ActivateNetworkProductionInput,
    ActivateNetworkProductionOutput,
    GetNetworkExecutionSnapshotInput,
    ListManagedNetworkVersionsInput,
    ListNetworkActivationsInput,
    ManagedNetworkVersion,
    NetworkProductionActivation,
    RollbackNetworkProductionInput,
)
from modules.network.application.interfaces.management_repository import (
    NetworkManagementRepository,
)
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError


class ListManagedNetworkVersionsUseCase:
    def __init__(self, repository: NetworkManagementRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: ListManagedNetworkVersionsInput,
    ) -> list[ManagedNetworkVersion]:
        versions = await self._repository.list_versions(
            input_dto.network_id,
            input_dto.project_id,
        )
        if not versions:
            state = await self._repository.get_production_state(
                input_dto.network_id,
                input_dto.project_id,
                lock=False,
            )
            if state is None:
                raise NotFoundError("Network not found")
        return versions


class ListNetworkActivationsUseCase:
    def __init__(self, repository: NetworkManagementRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: ListNetworkActivationsInput,
    ) -> list[NetworkProductionActivation]:
        state = await self._repository.get_production_state(
            input_dto.network_id,
            input_dto.project_id,
            lock=False,
        )
        if state is None:
            raise NotFoundError("Network not found")
        return await self._repository.list_activations(
            input_dto.network_id,
            input_dto.project_id,
        )


class GetNetworkExecutionSnapshotUseCase:
    def __init__(self, repository: NetworkManagementRepository) -> None:
        self._repository = repository

    async def execute(self, input_dto: GetNetworkExecutionSnapshotInput) -> dict:
        snapshot = await self._repository.get_execution_snapshot(
            input_dto.execution_id,
            input_dto.project_id,
        )
        if snapshot is None:
            raise NotFoundError("Network execution not found")
        return snapshot


class ActivateNetworkProductionUseCase:
    def __init__(self, repository: NetworkManagementRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: ActivateNetworkProductionInput,
    ) -> ActivateNetworkProductionOutput:
        description = input_dto.change_description.strip()
        if len(description) < 3:
            raise ValidationError("Production activation requires a change description")

        state = await self._repository.get_production_state(
            input_dto.network_id,
            input_dto.project_id,
            lock=True,
        )
        if state is None:
            raise NotFoundError("Network not found")
        if (
            input_dto.expected_current_production_version_id
            != state.production_version_id
        ):
            raise ConflictError(
                "Production changed after this release was selected. "
                "Review the current Production release again."
            )

        source = await self._repository.get_version(
            input_dto.source_version_id,
            input_dto.project_id,
        )
        if (
            source is None
            or source.network_id != input_dto.network_id
            or source.kind != "release"
        ):
            raise NotFoundError("Historical Network Release not found")
        if source.id == state.production_version_id:
            raise ConflictError("Selected Network Release is already in Production")

        previous = None
        if state.production_version_id is not None:
            previous = await self._repository.get_version(
                state.production_version_id,
                input_dto.project_id,
            )
        activation_kind = (
            "rollback"
            if previous is not None
            and previous.created_at is not None
            and source.created_at is not None
            and source.created_at < previous.created_at
            else "reactivate"
        )
        activation = await self._repository.activate_production(
            network_id=input_dto.network_id,
            project_id=input_dto.project_id,
            version_id=source.id,
            previous_version_id=state.production_version_id,
            activation_kind=activation_kind,
            change_description=description,
            created_by=input_dto.created_by,
        )
        return ActivateNetworkProductionOutput(
            version=source,
            activation=activation,
        )


class RollbackNetworkProductionUseCase:
    def __init__(self, repository: NetworkManagementRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: RollbackNetworkProductionInput,
    ) -> ManagedNetworkVersion:
        state = await self._repository.get_production_state(
            input_dto.network_id,
            input_dto.project_id,
            lock=True,
        )
        if state is None:
            raise NotFoundError("Network not found")

        target = await self._repository.get_version(
            input_dto.target_version_id,
            input_dto.project_id,
        )
        if (
            target is None
            or target.network_id != input_dto.network_id
            or target.kind != "release"
        ):
            raise NotFoundError("Historical Network Production version not found")
        if target.id == state.production_version_id:
            raise ConflictError("Selected Network version is already in Production")

        await self._repository.activate_production(
            network_id=input_dto.network_id,
            project_id=input_dto.project_id,
            version_id=target.id,
            previous_version_id=state.production_version_id,
            activation_kind="rollback",
            change_description=f"Rolled back Production to Network Release {target.version}.",
            created_by=input_dto.created_by,
        )
        return target
