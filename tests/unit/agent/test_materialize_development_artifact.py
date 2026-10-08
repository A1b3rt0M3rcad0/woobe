from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import CreatePromptInput, CreatePromptOutput
from modules.agent.application.use_cases.ai_prompt_cases import CreatePromptUseCase
from modules.agent.application.use_cases.materialize_development_artifact import (
    MaterializeDevelopmentArtifact,
)


class Repository:
    def __init__(self):
        self.rows = {}

    async def get_by_version(self, agent_id, version):
        return self.rows.get((agent_id, version))

    async def save(self, item):
        self.rows[(item.agent_id, item.version)] = item
        return item


@pytest.mark.asyncio
async def test_changed_author_prompt_allocates_immutable_version_and_retry_reuses_it():
    repository = Repository()
    materialize = MaterializeDevelopmentArtifact(
        repository,
        CreatePromptUseCase(repository),
        CreatePromptOutput,
        ("name", "content", "content_hash"),
    )
    original = CreatePromptInput(
        project_id=uuid4(), agent_id=uuid4(), version="1.0.0", content="Original"
    )
    first = await materialize.execute(original)
    changed = original.model_copy(update={"content": "Changed"})
    second = await materialize.execute(changed)
    retry = await materialize.execute(changed)
    assert first.version == "1.0.0"
    assert second.version.startswith("dev-") and len(second.version) == 32
    assert second.id != first.id and retry.id == second.id
    assert repository.rows[(original.agent_id, "1.0.0")].content == "Original"
    assert len(repository.rows) == 2


@pytest.mark.asyncio
async def test_same_content_in_another_agent_is_not_reused():
    repository = Repository()
    materialize = MaterializeDevelopmentArtifact(
        repository,
        CreatePromptUseCase(repository),
        CreatePromptOutput,
        ("name", "content", "content_hash"),
    )
    data = CreatePromptInput(
        project_id=uuid4(), agent_id=uuid4(), version="1.0.0", content="Same"
    )
    first = await materialize.execute(data)
    second = await materialize.execute(data.model_copy(update={"agent_id": uuid4()}))
    assert first.id != second.id
