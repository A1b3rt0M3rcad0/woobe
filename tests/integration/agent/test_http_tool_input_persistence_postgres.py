from __future__ import annotations

from uuid import uuid4

import pytest

from modules.agent.application.dtos.tools_dtos import CreateToolInput, UpdateToolInput
from modules.agent.application.use_cases.tools_use_cases import (
    CreateToolUseCase,
    UpdateToolUseCase,
)
from modules.agent.domain.enums import ToolType
from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.config import Settings
from shared.infra.database.session import create_engine


class _Outbox:
    def __init__(self) -> None:
        self.events = []

    async def write(self, event) -> None:
        self.events.append(event)


def _old_config() -> dict:
    return {
        "protocol": "http",
        "mode": "group",
        "schema_version": 2,
        "base_url": "https://api.mathjs.org",
        "routes": [
            {
                "id": "route-sum",
                "operation_id": "sum_2_numbers",
                "name": "Sum 2 numbers",
                "description": "Old model-provided operand",
                "method": "GET",
                "path": "/v4/?expr={{external_context.age}}%2B{{b}}",
                "default_permission": "allow",
            }
        ],
    }


def _runtime_only_config() -> dict:
    return {
        "protocol": "http",
        "mode": "group",
        "schema_version": 2,
        "base_url": "https://api.mathjs.org",
        "routes": [
            {
                "id": "route-sum",
                "operation_id": "sum_2_numbers",
                "name": "Sum 2 numbers",
                "description": "Runtime-only operands",
                "method": "GET",
                "path": (
                    "/v4/?expr={{external_context.age}}"
                    "%2B{{project_env.MOCKED_NUMBER}}"
                ),
                "default_permission": "allow",
            }
        ],
    }


@pytest.mark.asyncio
async def test_updated_http_route_does_not_resurrect_removed_agent_input_after_commit() -> None:
    engine = create_engine(Settings.model_validate({}))
    outbox = _Outbox()
    tool_id = None
    project_id = uuid4()

    try:
        async with AgentUnitOfWork(engine) as uow:
            creator = CreateToolUseCase(
                SQLAlchemyAgentToolRepository(uow),
                outbox,
            )
            created = await creator.execute(
                CreateToolInput(
                    project_id=project_id,
                    name="math-regression",
                    type=ToolType.HTTP,
                    config=_old_config(),
                )
            )
            tool_id = created.id

        async with AgentUnitOfWork(engine) as uow:
            updater = UpdateToolUseCase(
                SQLAlchemyAgentToolRepository(uow),
                outbox,
            )
            await updater.execute(
                tool_id,
                UpdateToolInput(
                    type=ToolType.HTTP,
                    config=_runtime_only_config(),
                ),
            )

        async with AgentUnitOfWork(engine) as uow:
            persisted = await SQLAlchemyAgentToolRepository(uow).get_by_id(tool_id)
            route = persisted.config["routes"][0]

            assert route["input_schema"] == {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            }
            assert "b" not in route["input_schema"]["properties"]
            assert "b" not in route["input_schema"]["required"]
            assert "{{b}}" not in route["path"]
            assert route["path"].endswith(
                "{{external_context.age}}%2B{{project_env.MOCKED_NUMBER}}"
            )
    finally:
        if tool_id is not None:
            async with AgentUnitOfWork(engine) as uow:
                await SQLAlchemyAgentToolRepository(uow).delete(tool_id)
        await engine.dispose()
