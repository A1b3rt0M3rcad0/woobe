from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import CreateReleaseInput
from modules.agent.application.use_cases.session_mode_compatible_release import (
    SessionModeCompatibleCreateReleaseUseCase,
)
from modules.agent.domain.enums import AgentStatus, Provider, SessionMode


@pytest.mark.asyncio
async def test_save_draft_synchronizes_server_canonical_runtime_config_to_agent() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    skill_id = uuid4()
    skill_version_id = uuid4()
    agent = SimpleNamespace(
        id=agent_id,
        project_id=project_id,
        name="Calculator",
        description="",
        system_prompt="Old prompt",
        provider=Provider.custom,
        model="deepseek-v4-flash",
        provider_credential_id=uuid4(),
        provider_model_id=uuid4(),
        fallback_provider=None,
        fallback_model=None,
        fallback_credential_id=None,
        fallback_provider_model_id=None,
        temperature=0.7,
        max_output_tokens=2048,
        session_mode=SessionMode.stateless,
        status=AgentStatus.active,
        settings={"runtime_config": {"legacy": True}},
    )
    requested_runtime = {
        "skills": {
            "bindings": [
                {
                    "skill_id": str(skill_id),
                    "skill_version_id": str(skill_version_id),
                    "enabled": True,
                }
            ],
            "snapshots": [],
        }
    }
    canonical_runtime = {
        **requested_runtime,
        "skills": {
            **requested_runtime["skills"],
            "snapshots": [
                {
                    "skill_id": str(skill_id),
                    "skill_version_id": str(skill_version_id),
                    "project_id": str(project_id),
                    "version": "1.0.0",
                    "package_hash": "server-frozen-hash",
                    "package": {"name": "calculate-method"},
                }
            ],
        },
    }
    saved_draft = SimpleNamespace(
        name="Calculator",
        description="Uses the saved Draft",
        system_prompt="Follow installed procedures.",
        response_format={"enabled": False, "type": "text"},
        provider="custom",
        model="deepseek-v4-flash",
        provider_credential_id=agent.provider_credential_id,
        provider_model_id=agent.provider_model_id,
        fallback_provider=None,
        fallback_model=None,
        fallback_credential_id=None,
        fallback_provider_model_id=None,
        base_url="https://provider.example/v1",
        temperature=0.2,
        max_output_tokens=1024,
        session_mode="stateless",
        agent_status="active",
        knowledge_version_id=None,
        runtime_config=canonical_runtime,
    )

    agent_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=agent),
        update=AsyncMock(return_value=agent),
    )
    delegate = SimpleNamespace(execute=AsyncMock(return_value=saved_draft))
    use_case = SessionModeCompatibleCreateReleaseUseCase(delegate, agent_repo)
    input_dto = CreateReleaseInput(
        project_id=project_id,
        agent_id=agent_id,
        version="draft",
        description="Uses the saved Draft",
        system_prompt="Follow installed procedures.",
        runtime_config=requested_runtime,
    )

    result = await use_case.execute(input_dto)

    delegated_input = delegate.execute.await_args.args[0]
    assert delegated_input.runtime_config == requested_runtime
    assert delegated_input.provider == "custom"
    assert delegated_input.model == "deepseek-v4-flash"
    assert delegated_input.session_mode == "stateless"
    assert result is saved_draft
    assert agent.settings["runtime_config"] == canonical_runtime
    assert agent.settings["base_url"] == "https://provider.example/v1"
    assert agent.system_prompt == "Follow installed procedures."
    agent_repo.update.assert_awaited_once_with(agent)
