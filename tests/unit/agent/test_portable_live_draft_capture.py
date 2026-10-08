from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.infra.database import portable_export_reader as owner


@pytest.mark.asyncio
async def test_draft_export_uses_live_definition_even_with_incomplete_saved_draft(monkeypatch):
    project_id, agent_id, credential_id = uuid4(), uuid4(), uuid4()
    agent = SimpleNamespace(id=agent_id, project_id=project_id, revision=3)
    stale = SimpleNamespace(id=uuid4(), model_spec_snapshot=None, model_spec_hash=None)
    session = SimpleNamespace(get=AsyncMock(return_value=agent), scalar=AsyncMock(return_value=stale))
    compiler = SimpleNamespace(
        definition=lambda _: pytest.fail("Draft export selected a stale saved snapshot"),
        validate_skills=lambda *_: None,
    )
    reader = owner.PortableAgentExportReader(None, compiler=compiler)
    live = {"runtime_config": {}, "provider_credential_id": str(credential_id), "system_prompt": "Current native edit", "model_spec_snapshot": {"model_id": "fake"}}
    reader._live_draft_definition = AsyncMock(return_value=live)
    reader._credential_intent = AsyncMock(return_value={"provider": "custom"})
    monkeypatch.setattr(owner, "authorize_export_read", AsyncMock())
    captured = await reader.capture_in_session(session, project_id=project_id, principal=object(), agent_id=agent_id, source="draft")
    assert captured["definition"]["system_prompt"] == "Current native edit"
    assert captured["definition"]["model_spec_snapshot"] == {"model_id": "fake"}
    assert captured["source"]["snapshot_id"] is None
    assert captured["source"]["version"] is None
    assert captured["source"]["draft_revision"] == 3
    reader._live_draft_definition.assert_awaited_once()
    session.scalar.assert_not_awaited()
    assert stale.model_spec_snapshot is None and stale.model_spec_hash is None


@pytest.mark.asyncio
@pytest.mark.parametrize("selector", [{"source": "staging"}, {"source": "release", "release_version": "1.2.0"}, {"source": "production"}, {"snapshot_id": uuid4()}])
async def test_historical_export_does_not_repair_from_live_draft(monkeypatch, selector):
    project_id, agent_id = uuid4(), uuid4()
    agent = SimpleNamespace(id=agent_id, project_id=project_id, revision=3)
    saved = SimpleNamespace(id=uuid4(), project_id=project_id, agent_id=agent_id)
    async def get(model, identifier):
        return agent if model is owner.AgentModel else saved
    session = SimpleNamespace(get=get, scalar=AsyncMock(return_value=saved))
    class HistoricalRead(Exception):
        pass
    def definition(record):
        assert record is saved
        raise HistoricalRead
    reader = owner.PortableAgentExportReader(None, compiler=SimpleNamespace(definition=definition))
    reader._live_draft_definition = AsyncMock(side_effect=AssertionError("used current draft for historical selector"))
    monkeypatch.setattr(owner, "authorize_export_read", AsyncMock())
    with pytest.raises(HistoricalRead):
        await reader.capture_in_session(session, project_id=project_id, principal=object(), agent_id=agent_id, **selector)
    reader._live_draft_definition.assert_not_awaited()
