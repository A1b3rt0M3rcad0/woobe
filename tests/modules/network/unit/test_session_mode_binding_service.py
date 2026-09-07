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


def _agent(project_id, agent_id, runtime_config):
    return SimpleNamespace(
        id=agent_id,
        project_id=project_id,
        status="active",
        settings={"runtime_config": runtime_config},
        system_prompt="Current prompt",
        provider="custom",
        model="deepseek-v4-flash",
        provider_credential_id=uuid4(),
        provider_model_id=uuid4(),
        fallback_provider=None,
        fallback_model=None,
        fallback_credential_id=None,
        fallback_provider_model_id=None,
        temperature=0.2,
        max_output_tokens=1024,
        session_mode="stateless",
    )


def _release(project_id, agent_id, runtime_config, *, status="draft", session_mode="stateless"):
    return SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        agent_id=agent_id,
        version="1.0.0",
        status=status,
        snapshot_kind="release" if status in {"released", "production"} else status,
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
        session_mode=session_mode,
        knowledge_version_id=None,
        runtime_config=runtime_config,
    )


def test_session_mode_value_accepts_only_runtime_contract_values() -> None:
    assert _session_mode_value("stateful") == "stateful"
    assert _session_mode_value("stateless") == "stateless"
    assert _session_mode_value("invalid") is None
    assert _session_mode_value(None) is None


@pytest.mark.asyncio
async def test_resolve_draft_bindings_uses_canonical_saved_skill_snapshot() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    node_id = uuid4()
    runtime_config = _skill_runtime(project_id, uuid4(), uuid4())
    agent = _agent(project_id, agent_id, runtime_config)
    draft_release = _release(project_id, agent_id, runtime_config)
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
    assert binding["binding_source"] == "draft"
    assert binding["draft_release_id"] == str(draft_release.id)
    assert binding["session_mode"] == "stateless"
    assert binding["snapshot_override"]["runtime_config"] == runtime_config


@pytest.mark.asyncio
async def test_resolve_draft_bindings_rejects_agent_projection_skill_drift() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    node_id = uuid4()
    skill_id = uuid4()
    agent = _agent(project_id, agent_id, _skill_runtime(project_id, skill_id, uuid4()))
    draft_release = _release(
        project_id,
        agent_id,
        _skill_runtime(project_id, skill_id, uuid4()),
    )
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
async def test_freeze_bindings_materializes_staging_snapshot_with_same_resolver() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    node_id = uuid4()
    runtime_config = {"tools": {"tool_ids": []}}
    agent = _agent(project_id, agent_id, runtime_config)
    release = _release(
        project_id,
        agent_id,
        runtime_config,
        status="staging",
        session_mode="stateful",
    )
    session = AsyncMock()
    session.execute.side_effect = [
        _ScalarResult([release]),
        _ScalarResult([agent]),
    ]
    bindings = {
        str(node_id): {
            "node_id": str(node_id),
            "agent_id": str(agent_id),
            "release_id": str(release.id),
        }
    }

    await NetworkApplicationService._freeze_bindings(
        session,
        project_id=project_id,
        bindings=bindings,
        environment="staging",
    )

    binding = bindings[str(node_id)]
    assert binding["binding_source"] == "staging"
    assert binding["session_mode"] == "stateful"
    assert binding["snapshot_override"]["runtime_config"] == runtime_config
    assert binding["snapshot_override"]["model"] == release.model


@pytest.mark.asyncio
async def test_freeze_bindings_rejects_staging_snapshot_in_production() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    node_id = uuid4()
    agent = _agent(project_id, agent_id, {})
    release = _release(project_id, agent_id, {}, status="staging")
    session = AsyncMock()
    session.execute.side_effect = [
        _ScalarResult([release]),
        _ScalarResult([agent]),
    ]
    bindings = {
        str(node_id): {
            "node_id": str(node_id),
            "agent_id": str(agent_id),
            "release_id": str(release.id),
        }
    }

    with pytest.raises(ConflictError, match="immutable Agent Release"):
        await NetworkApplicationService._freeze_bindings(
            session,
            project_id=project_id,
            bindings=bindings,
            environment="production",
        )
