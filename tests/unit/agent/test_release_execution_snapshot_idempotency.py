from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from modules.agent.application.use_cases.auto_compatible_release_lifecycle import AutoCompatibleReleaseLifecycleUseCase
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus


class Repo:
    def __init__(self, items):
        self.items = {item.id: item for item in items}

    async def save(self, item):
        self.items[item.id] = item
        return item

    async def get_by_id(self, item_id: UUID):
        return self.items.get(item_id)

    async def get_by_version(self, agent_id: UUID, version: str):
        return next((item for item in self.items.values() if item.agent_id == agent_id and item.version == version), None)

    async def get_active_production(self, agent_id: UUID):
        matches = await self.list_by_status(agent_id, ReleaseStatus.production)
        return matches[0] if matches else None

    async def list_by_agent(self, agent_id: UUID):
        return [item for item in self.items.values() if item.agent_id == agent_id]

    async def paginate_by_agent(self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None):
        raise NotImplementedError

    async def list_by_status(self, agent_id: UUID, status: ReleaseStatus):
        return [item for item in self.items.values() if item.agent_id == agent_id and item.status == status]

    async def get_last_promoted(self, agent_id: UUID, *, exclude_id: UUID):
        return None

    async def delete(self, item_id: UUID):
        self.items.pop(item_id, None)


def release(project_id, agent_id, version, status, temperature):
    item = AgentRelease(
        project_id=project_id,
        agent_id=agent_id,
        version=version,
        status=status,
        provider="openai",
        model="gpt-4o-mini",
        system_prompt="prompt",
        response_format={"type": "json", "schema": {"message": "string"}},
        output_schema={"message": "string"},
        temperature=temperature,
    )
    item.snapshot_kind = (
        "draft"
        if status == ReleaseStatus.draft
        else "staging"
        if status == ReleaseStatus.staging
        else "release"
    )
    return item


@pytest.mark.asyncio
async def test_changed_execution_config_is_not_treated_as_unchanged_staging() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    production = release(project_id, agent_id, "v1.0.20260620.00", ReleaseStatus.production, 0.2)
    staging = release(project_id, agent_id, "staging", ReleaseStatus.staging, 0.9)
    repo = Repo([production, staging])
    use_case = AutoCompatibleReleaseLifecycleUseCase(repo)

    result = await use_case.execute(agent_id, staging.id, target_status="production", copy_snapshot=True)

    assert result.id != production.id
    assert result.version.startswith("v1.0.")
    assert production.status == ReleaseStatus.released
    assert len(await repo.list_by_agent(agent_id)) == 3
