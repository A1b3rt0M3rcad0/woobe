from __future__ import annotations

import ast
import inspect
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


def test_create_agent_composer_wires_default_context_manager_setting() -> None:
    from modules.agent.composition.composers.create_agent_composer import (
        create_agent_composer,
    )

    tree = ast.parse(inspect.getsource(create_agent_composer))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "CreateAgentUseCase"
    ]

    assert len(calls) == 1
    keyword = next(
        item
        for item in calls[0].keywords
        if item.arg == "default_context_manager"
    )
    assert isinstance(keyword.value, ast.Attribute)
    assert keyword.value.attr == "default_context_manager"
    assert isinstance(keyword.value.value, ast.Name)
    assert keyword.value.value.id == "SETTINGS"
