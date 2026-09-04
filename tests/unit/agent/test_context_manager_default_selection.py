from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import CreateAgentInput
from modules.agent.application.use_cases import CreateAgentUseCase


def _deps():
    agent_repo = SimpleNamespace(save=AsyncMock())

    async def save(agent):
        return agent

    agent_repo.save.side_effect = save
    credential_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    outbox = SimpleNamespace(write=AsyncMock())
    return agent_repo, credential_repo, outbox


@pytest.mark.asyncio
async def test_create_agent_freezes_system_default_selection_and_strategy() -> None:
    agent_repo, credential_repo, outbox = _deps()
    use_case = CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        default_context_manager="stdcm:v1",
    )

    saved = await use_case.execute(
        CreateAgentInput(
            project_id=uuid4(),
            name="Default Context Agent",
            model="test-model",
        )
    )

    assert saved.settings["runtime_config"]["context_assembler"] == {
        "name": "default",
        "version": "v1",
        "strategy_name": "stdcm",
        "strategy_version": "v1",
    }


@pytest.mark.asyncio
async def test_create_agent_preserves_explicit_context_manager_selection() -> None:
    agent_repo, credential_repo, outbox = _deps()
    use_case = CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        default_context_manager="stdcm:v1",
    )

    saved = await use_case.execute(
        CreateAgentInput(
            project_id=uuid4(),
            name="Explicit Context Agent",
            model="test-model",
            settings={
                "runtime_config": {
                    "context_assembler": {
                        "name": "stdcm",
                        "version": "v1",
                    }
                }
            },
        )
    )

    assert saved.settings["runtime_config"]["context_assembler"] == {
        "name": "stdcm",
        "version": "v1",
        "strategy_name": "stdcm",
        "strategy_version": "v1",
    }
