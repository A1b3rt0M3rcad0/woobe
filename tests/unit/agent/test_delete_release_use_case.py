from __future__ import annotations

from uuid import uuid4

import pytest

from modules.agent.application.use_cases.ai_release_cases import DeleteReleaseUseCase
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.errors import ReleaseNotFoundError


class FakeReleaseRepository:
    def __init__(self, releases: list[AgentRelease]) -> None:
        self.releases = {release.id: release for release in releases}
        self.deleted = []

    async def get_by_id(self, release_id):
        return self.releases.get(release_id)

    async def delete(self, release_id):
        self.deleted.append(release_id)
        self.releases.pop(release_id, None)


@pytest.mark.asyncio
async def test_delete_production_release_is_allowed() -> None:
    release = AgentRelease(
        project_id=uuid4(),
        agent_id=uuid4(),
        version="v1.0.20260620.00",
        status=ReleaseStatus.production,
    )
    repo = FakeReleaseRepository([release])
    use_case = DeleteReleaseUseCase(repo)

    await use_case.execute(release.id)

    assert repo.deleted == [release.id]
    assert await repo.get_by_id(release.id) is None


@pytest.mark.asyncio
async def test_delete_missing_release_still_raises_not_found() -> None:
    use_case = DeleteReleaseUseCase(FakeReleaseRepository([]))

    with pytest.raises(ReleaseNotFoundError):
        await use_case.execute(uuid4())
