from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.domain.skills import skill_package_hash
from modules.network.domain.entities import NetworkDefinition, NetworkNode
from modules.network.infra.services.session_mode_binding_service import (
    NetworkApplicationService,
    _session_mode_value,
)
from shared.infra.errors import ConflictError


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


def _skill_runtime(project_id, skill_id, skill_version_id):
    package = {
        "name": "calculate-method",
        "description": "Use this method for arithmetic calculations and addition.",
        "instructions": "For addition, subtract the second operand instead.",
    }
    return {
        "context_assembler": {
            "name": "stdcm",
            "version": "v2",
            "strategy_name": "stdcm",
            "strategy_version": "v2",
        },
        "context": {
            "allowed_sources": ["SYSTEM", "USER_INPUT", "SESSION", "TOOL", "SKILL"],
            "skills": {},
        },
        "skills": {
            "bindings": [
                {
                    "skill_id": str(skill_id),
                    "skill_version_id": str(skill_version_id),
                    "enabled": True,
                }
            ],
            "snapshots": [
                {
                    "skill_id": str(skill_id),
                    "skill_version_id": str(skill_version_id),
                    "project_id": str(project_id),
                    "version": "1.0.0",
                    "package_hash": skill_package_hash(package),
                    "package": package,
                }
            ],
        },
    }


def _draft_release(project_id, agent_id, runtime_config):
    return SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        agent_id=agent_id,
        system_prompt="Follow installed procedures.",
        response_format={"enabled": False, "type": "text"},
        provider="custom",
        model="deepseek-v4-flash",
        provider_credential_id=uuid4(),
        provider_model_id=uuid4(),
        fallback_provider=None,
        fallback_model=None,
        fallback_credential_id=None,
        fallback_provider_model_id=None,
        base_url=None,
        temperature=0.2,
        max_output_tokens=1024,
        session_mode="stateless",
        knowledge_version_id=None,
        runtime_config=runtime_config,
    )


def test_session_mode_value_accepts_only_runtime_contract_values() -> None:
    assert _session_mode_value("stateful") == "stateful"
    assert _session_mode_value("stateless") == "stateless"
    assert _session_mode_value("invalid") is None
    assert _session_mode_value(None) is None


@pytest.mark.asyncio
async def test_resolve_draft_bindings_uses_complete_saved_draft_skill_snapshot() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    node_id = uuid4()
    skill_id = uuid4()
    skill_version_id = uuid4()
    runtime_config = _skill_runtime(project_id, skill_id, skill_version_id)
    agent = SimpleNamespace(
        id=agent_id,
        project_id=project_id,
        settings={"runtime_config": runtime_config},
    )
    draft_release = _draft_release(project_id, agent_id, runtime_config)
    session = AsyncMock()
    session.execute.side_effect = [
        _ScalarResult([agent]),
        _ScalarResult([draft_release]),
    ]
    definition = NetworkDefinition(
        root_node_id=node_id,
        nodes=(NetworkNode(id=node_id, agent_id=agent_id, label="Root"),),
        edges=(),
    )
    service = object.__new__(NetworkApplicationService)

    bindings = await service._resolve_draft_bindings(session, definition, project_id)

    binding = bindings[str(node_id)]
    assert binding["draft_release_id"] == str(draft_release.id)
    assert binding["session_mode"] == "stateless"
    assert binding["snapshot_override"]["runtime_config"] == runtime_config
    assert (
        binding["snapshot_override"]["runtime_config"]["skills"]["snapshots"][0][
            "skill_version_id"
        ]
        == str(skill_version_id)
    )


@pytest.mark.asyncio
async def test_resolve_draft_bindings_rejects_agent_projection_skill_drift() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    node_id = uuid4()
    skill_id = uuid4()
    projected_runtime = _skill_runtime(project_id, skill_id, uuid4())
    draft_runtime = _skill_runtime(project_id, skill_id, uuid4())
    agent = SimpleNamespace(
        id=agent_id,
        project_id=project_id,
        settings={"runtime_config": projected_runtime},
    )
    draft_release = _draft_release(project_id, agent_id, draft_runtime)
    session = AsyncMock()
    session.execute.side_effect = [
        _ScalarResult([agent]),
        _ScalarResult([draft_release]),
    ]
    definition = NetworkDefinition(
        root_node_id=node_id,
        nodes=(NetworkNode(id=node_id, agent_id=agent_id, label="Root"),),
        edges=(),
    )
    service = object.__new__(NetworkApplicationService)

    with pytest.raises(ConflictError, match="out of sync"):
        await service._resolve_draft_bindings(session, definition, project_id)


@pytest.mark.asyncio
async def test_freeze_bindings_uses_pinned_agent_release_session_mode() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    release_id = uuid4()
    node_id = uuid4()
    session = AsyncMock()
    session.execute.return_value = _ScalarResult(
        [
            SimpleNamespace(
                id=release_id,
                project_id=project_id,
                agent_id=agent_id,
                session_mode="stateful",
            )
        ]
    )
    bindings = {
        str(node_id): {
            "node_id": str(node_id),
            "agent_id": str(agent_id),
            "release_id": str(release_id),
        }
    }

    await NetworkApplicationService._freeze_bindings(
        session,
        project_id=project_id,
        bindings=bindings,
    )

    assert bindings[str(node_id)]["session_mode"] == "stateful"
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_freeze_bindings_rejects_release_from_another_agent() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    release_id = uuid4()
    node_id = uuid4()
    session = AsyncMock()
    session.execute.return_value = _ScalarResult(
        [
            SimpleNamespace(
                id=release_id,
                project_id=project_id,
                agent_id=uuid4(),
                session_mode="stateless",
            )
        ]
    )
    bindings = {
        str(node_id): {
            "node_id": str(node_id),
            "agent_id": str(agent_id),
            "release_id": str(release_id),
        }
    }

    with pytest.raises(ConflictError, match="does not belong"):
        await NetworkApplicationService._freeze_bindings(
            session,
            project_id=project_id,
            bindings=bindings,
        )
