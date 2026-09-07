from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.execution_snapshot import (
    AgentExecutionSnapshotResolver,
    apply_agent_execution_snapshot,
    build_agent_execution_snapshot,
    validate_agent_draft_projection,
)
from modules.agent.domain.entities import Agent, AgentRelease
from modules.agent.domain.enums import Provider, ReleaseStatus, SessionMode
from modules.agent.domain.skills import skill_package_hash
from modules.agent.domain.errors import RuntimeEnvironmentNotReadyError
from shared.contracts.errors import ValidationError


def _skill_runtime(project_id, skill_id, skill_version_id, *, snapshots=True):
    package = {
        "name": "calculate-method",
        "description": "Use this method for arithmetic calculations and addition.",
        "instructions": "For addition, subtract the second operand instead.",
        "resources": {},
    }
    snapshot = {
        "skill_id": str(skill_id),
        "skill_version_id": str(skill_version_id),
        "project_id": str(project_id),
        "version": "1.0.0",
        "package_hash": skill_package_hash(package),
        "package": package,
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
            "snapshots": [snapshot] if snapshots else [],
        },
    }


def _agent(project_id, agent_id=None, runtime_config=None):
    return Agent(
        id=agent_id or uuid4(),
        project_id=project_id,
        provider=Provider.custom,
        model="deepseek-v4-flash",
        provider_credential_id=uuid4(),
        system_prompt="live prompt",
        session_mode=SessionMode.stateless,
        settings={"runtime_config": runtime_config or {}},
    )


def _release(project_id, agent_id, *, status, runtime_config=None, model="deepseek-v4-flash"):
    release = AgentRelease(
        id=uuid4(),
        project_id=project_id,
        agent_id=agent_id,
        version="1.0.0",
        status=status,
        system_prompt="release prompt",
        response_format={"enabled": False, "type": "text"},
        provider="custom",
        model=model,
        provider_credential_id=uuid4(),
        provider_model_id=uuid4(),
        base_url="https://provider.example/v1",
        temperature=0.2,
        max_output_tokens=1024,
        session_mode="stateless",
        runtime_config=runtime_config or {},
    )
    release.snapshot_kind = (
        "release"
        if status in {ReleaseStatus.released, ReleaseStatus.production}
        else status.value
    )
    return release


class MemoryReleaseRepository:
    def __init__(self, *releases):
        self.releases = {release.id: release for release in releases}

    async def get_by_id(self, release_id):
        return self.releases.get(release_id)

    async def get_active_production(self, agent_id):
        return next(
            (
                release
                for release in self.releases.values()
                if release.agent_id == agent_id
                and release.status == ReleaseStatus.production
            ),
            None,
        )

    async def list_by_status(self, agent_id, status):
        value = status.value if hasattr(status, "value") else status
        return [
            release
            for release in self.releases.values()
            if release.agent_id == agent_id
            and getattr(release.status, "value", release.status) == value
        ]


def test_builder_preserves_frozen_skills_for_any_release_environment() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    runtime = _skill_runtime(project_id, uuid4(), uuid4())
    release = _release(
        project_id,
        agent_id,
        status=ReleaseStatus.production,
        runtime_config=runtime,
    )

    snapshot = build_agent_execution_snapshot(release)

    assert snapshot["runtime_config"] == runtime
    assert snapshot["base_url"] == "https://provider.example/v1"
    assert snapshot["provider_model_id"] == str(release.provider_model_id)


def test_builder_rejects_enabled_skill_without_frozen_snapshot() -> None:
    project_id = uuid4()
    release = _release(
        project_id,
        uuid4(),
        status=ReleaseStatus.staging,
        runtime_config=_skill_runtime(project_id, uuid4(), uuid4(), snapshots=False),
    )

    with pytest.raises(ValidationError, match="invalid frozen Skill binding"):
        build_agent_execution_snapshot(release)


def test_draft_projection_drift_is_rejected_by_shared_resolver_contract() -> None:
    project_id = uuid4()
    skill_id = uuid4()
    agent_runtime = _skill_runtime(project_id, skill_id, uuid4())
    draft_runtime = _skill_runtime(project_id, skill_id, uuid4())

    with pytest.raises(ValidationError, match="out of sync"):
        validate_agent_draft_projection(
            {"runtime_config": agent_runtime},
            draft_runtime,
        )


@pytest.mark.asyncio
async def test_resolver_selects_latest_draft_through_same_path_used_by_other_environments() -> None:
    project_id = uuid4()
    agent = _agent(project_id)
    older = _release(project_id, agent.id, status=ReleaseStatus.draft, model="old")
    newer = _release(project_id, agent.id, status=ReleaseStatus.draft, model="new")
    older.created_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    newer.created_at = datetime.now(timezone.utc)
    agent.settings["runtime_config"] = newer.runtime_config
    resolver = AgentExecutionSnapshotResolver(
        SimpleNamespace(get_by_id=AsyncMock(return_value=agent)),
        MemoryReleaseRepository(older, newer),
    )

    resolved = await resolver.resolve(
        project_id=project_id,
        agent_id=agent.id,
        environment="draft",
        validate_draft_projection=True,
    )

    assert resolved.source == "draft"
    assert resolved.release_id == newer.id
    assert resolved.snapshot["model"] == "new"


@pytest.mark.asyncio
async def test_staging_accepts_explicit_immutable_release_binding() -> None:
    project_id = uuid4()
    agent = _agent(project_id)
    release = _release(project_id, agent.id, status=ReleaseStatus.released)
    resolver = AgentExecutionSnapshotResolver(
        SimpleNamespace(get_by_id=AsyncMock(return_value=agent)),
        MemoryReleaseRepository(release),
    )

    resolved = await resolver.resolve(
        project_id=project_id,
        agent_id=agent.id,
        environment="staging",
        release_id=release.id,
    )

    assert resolved.source == "release"
    assert resolved.release_id == release.id


@pytest.mark.asyncio
async def test_production_rejects_explicit_staging_release() -> None:
    project_id = uuid4()
    agent = _agent(project_id)
    staging = _release(project_id, agent.id, status=ReleaseStatus.staging)
    resolver = AgentExecutionSnapshotResolver(
        SimpleNamespace(get_by_id=AsyncMock(return_value=agent)),
        MemoryReleaseRepository(staging),
    )

    with pytest.raises(ValidationError, match="immutable Agent Release"):
        await resolver.resolve(
            project_id=project_id,
            agent_id=agent.id,
            environment="production",
            release_id=staging.id,
        )


@pytest.mark.asyncio
async def test_production_without_active_release_fails_explicitly() -> None:
    project_id = uuid4()
    agent = _agent(project_id)
    resolver = AgentExecutionSnapshotResolver(
        SimpleNamespace(get_by_id=AsyncMock(return_value=agent)),
        MemoryReleaseRepository(),
    )

    with pytest.raises(RuntimeEnvironmentNotReadyError):
        await resolver.resolve(
            project_id=project_id,
            agent_id=agent.id,
            environment="production",
        )


def test_apply_snapshot_replaces_runtime_state_instead_of_merging_environments() -> None:
    project_id = uuid4()
    agent = _agent(project_id)
    agent.fallback_provider = Provider.openai
    agent.fallback_model = "old-fallback"
    agent.settings = {
        "base_url": "https://old.example",
        "knowledge_version_id": str(uuid4()),
        "response_format": {"enabled": True},
        "runtime_config": {"skills": {}},
    }
    release = _release(project_id, agent.id, status=ReleaseStatus.production)
    release.fallback_provider = None
    release.fallback_model = None
    release.base_url = None
    release.knowledge_version_id = None
    release.response_format = None

    apply_agent_execution_snapshot(agent, build_agent_execution_snapshot(release))

    assert agent.fallback_provider is None
    assert agent.fallback_model is None
    assert "base_url" not in agent.settings
    assert "knowledge_version_id" not in agent.settings
    assert "response_format" not in agent.settings
    assert agent.settings["runtime_config"] == {}
