from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from modules.agent.application.use_cases.auto_compatible_release_lifecycle import (
    AutoCompatibleReleaseLifecycleUseCase,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus


class FakeReleaseRepository:
    def __init__(self, releases: list[AgentRelease]) -> None:
        self.releases = {release.id: release for release in releases}

    async def save(self, release: AgentRelease) -> AgentRelease:
        self.releases[release.id] = release
        return release

    async def get_by_id(self, release_id: UUID) -> AgentRelease | None:
        return self.releases.get(release_id)

    async def get_by_version(self, agent_id: UUID, version: str) -> AgentRelease | None:
        for release in self.releases.values():
            if release.agent_id == agent_id and release.version == version:
                return release
        return None

    async def get_active_production(self, agent_id: UUID) -> AgentRelease | None:
        matches = await self.list_by_status(agent_id, ReleaseStatus.production)
        return matches[0] if matches else None

    async def list_by_agent(self, agent_id: UUID) -> list[AgentRelease]:
        return [release for release in self.releases.values() if release.agent_id == agent_id]

    async def paginate_by_agent(self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None):
        raise NotImplementedError

    async def list_by_status(self, agent_id: UUID, status: ReleaseStatus) -> list[AgentRelease]:
        return [
            release
            for release in self.releases.values()
            if release.agent_id == agent_id and release.status == status
        ]

    async def get_last_promoted(self, agent_id: UUID, *, exclude_id: UUID) -> AgentRelease | None:
        return None

    async def delete(self, release_id: UUID) -> None:
        self.releases.pop(release_id, None)


@pytest.mark.asyncio
async def test_production_from_staging_renamed_abbreviated_output_key_bumps_compatibility() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    production = AgentRelease(
        project_id=project_id,
        agent_id=agent_id,
        version="v0.0.20260620.00",
        status=ReleaseStatus.production,
        output_schema={"message": "string"},
    )
    staging = AgentRelease(
        project_id=project_id,
        agent_id=agent_id,
        version="staging",
        status=ReleaseStatus.staging,
        output_schema={"messagev2": "string"},
    )
    repo = FakeReleaseRepository([production, staging])
    use_case = AutoCompatibleReleaseLifecycleUseCase(repo)

    result = await use_case.execute(
        agent_id,
        staging.id,
        target_status="production",
        copy_snapshot=True,
    )

    assert result.version.startswith("v1.0.")
    assert result.status == ReleaseStatus.production
    assert production.status == ReleaseStatus.archived
