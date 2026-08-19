from modules.agent.application.dtos.ai_dtos import (
    CreateReleaseTestOutput,
    ListReleasesOutput,
    ListReleaseTestsOutput,
)
from modules.agent.application.interfaces.repositories import (
    AgentReleaseRepository,
    AgentReleaseTestRepository,
)
from modules.agent.application.use_cases.auto_compatible_release_lifecycle import (
    AutoCompatibleReleaseLifecycleUseCase as PromoteReleaseUseCase,
)
from modules.agent.application.use_cases.release_lifecycle_use_cases import (
    AutoCreateReleaseUseCase as CreateReleaseUseCase,
    _release_to_output,
)
from modules.agent.domain.entities import AgentReleaseTest
from modules.agent.domain.enums import ReleaseStatus, ReleaseTestStatus
from shared.contracts.errors import ConflictError

__all__ = [
    "CreateReleaseUseCase",
    "ListReleasesUseCase",
    "GetReleaseUseCase",
    "PromoteReleaseUseCase",
    "RollbackReleaseUseCase",
    "CreateReleaseTestUseCase",
    "ListReleaseTestsUseCase",
    "GetReleaseTestUseCase",
    "DeleteReleaseUseCase",
    "_release_to_output",
]


class RollbackReleaseUseCase(PromoteReleaseUseCase):
    pass


class ListReleasesUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, agent_id):
        return [
            ListReleasesOutput(**_release_to_output(item).model_dump())
            for item in await self._release_repo.list_by_agent(agent_id)
        ]


class GetReleaseUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, release_id):
        item = await self._release_repo.get_by_id(release_id)
        if item is None:
            from modules.agent.domain.errors import ReleaseNotFoundError
            raise ReleaseNotFoundError
        return item


class DeleteReleaseUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, release_id):
        item = await self._release_repo.get_by_id(release_id)
        if item is None:
            from modules.agent.domain.errors import ReleaseNotFoundError
            raise ReleaseNotFoundError
        if (
            item.status != ReleaseStatus.draft
            or getattr(item, "snapshot_kind", "draft") != "draft"
        ):
            raise ConflictError(
                "Staging, published and historical Agent snapshots are immutable and cannot be deleted"
            )
        await self._release_repo.delete(release_id)


class CreateReleaseTestUseCase:
    def __init__(self, test_repo: AgentReleaseTestRepository) -> None:
        self._test_repo = test_repo

    async def execute(self, input_dto):
        item = AgentReleaseTest(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            release_id=input_dto.release_id,
            contract_version_id=input_dto.contract_version_id,
            input_payload=input_dto.input_payload,
            expected_output=input_dto.expected_output,
            status=ReleaseTestStatus.pending,
        )
        saved = await self._test_repo.save(item)
        return CreateReleaseTestOutput(
            id=saved.id,
            project_id=saved.project_id,
            agent_id=saved.agent_id,
            release_id=saved.release_id,
            contract_version_id=saved.contract_version_id,
            input_payload=saved.input_payload,
            expected_output=saved.expected_output,
            actual_output=saved.actual_output,
            status=saved.status,
            validation_errors=saved.validation_errors,
            latency_ms=saved.latency_ms,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class ListReleaseTestsUseCase:
    def __init__(self, test_repo: AgentReleaseTestRepository) -> None:
        self._test_repo = test_repo

    async def execute(self, release_id):
        return [
            ListReleaseTestsOutput(
                id=item.id,
                release_id=item.release_id,
                contract_version_id=item.contract_version_id,
                status=item.status,
                validation_errors=item.validation_errors,
                latency_ms=item.latency_ms,
                created_at=item.created_at,
            )
            for item in await self._test_repo.list_by_release(release_id)
        ]


class GetReleaseTestUseCase:
    def __init__(self, test_repo: AgentReleaseTestRepository) -> None:
        self._test_repo = test_repo

    async def execute(self, test_id):
        item = await self._test_repo.get_by_id(test_id)
        if item is None:
            from modules.agent.domain.errors import ReleaseTestNotFoundError
            raise ReleaseTestNotFoundError
        return item
