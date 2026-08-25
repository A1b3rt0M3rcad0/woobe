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


def make_release(*, project_id, agent_id, version, status, output_schema=None, system_prompt="prompt"):
    release = AgentRelease(
        project_id=project_id,
        agent_id=agent_id,
        version=version,
        status=status,
        output_schema=output_schema,
        response_format={"type": "json", "schema": output_schema} if output_schema else None,
        system_prompt=system_prompt,
        provider="openai",
        model="gpt-4o-mini",
    )
    release.snapshot_kind = (
        "draft"
        if status == ReleaseStatus.draft
        else "staging"
        if status == ReleaseStatus.staging
        else "release"
    )
    return release


@pytest.mark.asyncio
async def test_production_from_staging_renamed_abbreviated_output_key_bumps_compatibility() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    production = make_release(
        project_id=project_id,
        agent_id=agent_id,
        version="v0.0.20260620.00",
        status=ReleaseStatus.production,
        output_schema={"message": "string"},
    )
    staging = make_release(
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
        copy_snapshot=False,
    )

    assert result.version.startswith("v1.0.")
    assert result.status == ReleaseStatus.production
    assert production.status == ReleaseStatus.released


@pytest.mark.asyncio
async def test_deploy_archived_release_restores_existing_version_without_new_version() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    production = make_release(project_id=project_id, agent_id=agent_id, version="v1.0.20260620.00", status=ReleaseStatus.production)
    archived = make_release(project_id=project_id, agent_id=agent_id, version="v0.0.20260619.00", status=ReleaseStatus.archived)
    repo = FakeReleaseRepository([production, archived])
    use_case = AutoCompatibleReleaseLifecycleUseCase(repo)

    result = await use_case.execute(agent_id, archived.id, target_status="production", copy_snapshot=False)

    assert result.id == archived.id
    assert result.version == "v0.0.20260619.00"
    assert archived.status == ReleaseStatus.production
    assert production.status == ReleaseStatus.released
    assert len(await repo.list_by_agent(agent_id)) == 2


@pytest.mark.asyncio
async def test_deploy_active_production_is_not_a_new_release() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    production = make_release(project_id=project_id, agent_id=agent_id, version="v1.0.20260620.00", status=ReleaseStatus.production)
    repo = FakeReleaseRepository([production])
    use_case = AutoCompatibleReleaseLifecycleUseCase(repo)

    result = await use_case.execute(agent_id, production.id, target_status="production", copy_snapshot=False)

    assert result.id == production.id
    assert result.version == "v1.0.20260620.00"
    assert len(await repo.list_by_agent(agent_id)) == 1


@pytest.mark.asyncio
async def test_releasing_unchanged_staging_is_idempotent() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    production = make_release(
        project_id=project_id,
        agent_id=agent_id,
        version="v1.0.20260620.00",
        status=ReleaseStatus.production,
        output_schema={"message": "string"},
    )
    staging = make_release(
        project_id=project_id,
        agent_id=agent_id,
        version="staging",
        status=ReleaseStatus.staging,
        output_schema={"message": "string"},
    )
    repo = FakeReleaseRepository([production, staging])
    use_case = AutoCompatibleReleaseLifecycleUseCase(repo)

    result = await use_case.execute(agent_id, staging.id, target_status="production", copy_snapshot=True)

    assert result.id == production.id
    assert result.version == "v1.0.20260620.00"
    assert production.status == ReleaseStatus.production
    assert len(await repo.list_by_agent(agent_id)) == 2
