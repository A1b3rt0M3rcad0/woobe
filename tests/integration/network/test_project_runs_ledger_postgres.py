from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.infra.database.models import AgentModel
from modules.core.infra.database.models import ProjectModel
from modules.core.infra.database.project_runs_reader import SQLProjectRunsReader
from modules.network.infra.database.models import (
    NetworkModel,
    NetworkSessionModel,
)
from modules.network.infra.services.service import NetworkApplicationService
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


@pytest.mark.asyncio
async def test_event_journal_network_acceptance_is_immediately_visible_in_project_runs() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    agent_id = uuid4()
    network_id = uuid4()
    network_session_id = uuid4()
    node_id = uuid4()

    definition = {
        "schema_version": 2,
        "root_node_id": str(node_id),
        "nodes": [
            {
                "id": str(node_id),
                "agent_id": str(agent_id),
                "label": "Ledger Agent",
                "capability_description": "Exercise Network Run acceptance.",
                "position": {"x": 0.0, "y": 0.0},
                "binding": {"source": "draft", "release_id": None},
            }
        ],
        "edges": [],
        "settings": {
            "session_mode": "stateless",
            "max_depth": 2,
            "max_invocations": 4,
            "timeout_seconds": 30,
        },
    }

    async with session_factory() as session, session.begin():
        session.add(
            ProjectModel(
                id=project_id,
                workspace_id=uuid4(),
                name="Network Run ledger project",
                slug=f"network-run-ledger-{project_id}",
                status="active",
                data={},
            )
        )
        await session.flush()

        session.add(
            AgentModel(
                id=agent_id,
                project_id=project_id,
                provider_credential_id=None,
                fallback_credential_id=None,
                name="Ledger Agent",
                description="",
                type="assistant",
                system_prompt="",
                provider="openai",
                model="test",
                fallback_provider=None,
                fallback_model=None,
                temperature=0.2,
                max_output_tokens=128,
                session_mode="stateless",
                status="active",
                settings={},
            )
        )
        await session.flush()

        session.add(
            NetworkModel(
                id=network_id,
                project_id=project_id,
                name="Ledger Network",
                description="",
                draft_definition=definition,
                draft_revision=1,
                staging_version_id=None,
                production_version_id=None,
            )
        )
        await session.flush()

        session.add(
            NetworkSessionModel(
                id=network_session_id,
                network_id=network_id,
                network_version_id=None,
                project_id=project_id,
                origin="runtime_api",
                environment="draft",
                title="Ledger session",
                tenant_id=None,
                user_id=None,
                external_session_id=None,
                status="active",
            )
        )

    service = NetworkApplicationService(
        session_factory,
        run_storage_version=EVENT_JOURNAL_STORAGE_VERSION,
    )
    submitted = await service.submit_execution(
        network_id=network_id,
        project_id=project_id,
        network_session_id=network_session_id,
        message="hello network ledger",
        idempotency_key=f"ledger-{uuid4()}",
        expected_draft_revision=1,
    )

    assert submitted.storage_version == EVENT_JOURNAL_STORAGE_VERSION
    assert submitted.status == "queued"

    async with session_factory() as session:
        ledger = await SQLProjectRunsReader(
            SimpleNamespace(session=session)
        ).fetch(
            project_id=project_id,
            network_id=None,
            limit=100,
        )

    assert ledger["summary"]["network_runs"] == 1
    assert ledger["summary"]["top_level_runs"] == 1
    assert ledger["summary"]["active_top_level_runs"] == 1
    assert ledger["summary"]["direct_agent_runs"] == 0
    assert ledger["summary"]["network_agent_runs"] == 0
    assert len(ledger["network_runs"]) == 1
    assert ledger["network_runs"][0]["id"] == str(submitted.id)
    assert ledger["network_runs"][0]["network_id"] == str(network_id)
    assert ledger["network_runs"][0]["status"] == "queued"
    assert ledger["network_runs"][0]["agent_runs"] == []

    await engine.dispose()
