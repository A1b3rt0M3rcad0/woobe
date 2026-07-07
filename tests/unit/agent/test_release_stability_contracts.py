from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.tool_release_snapshots import tool_to_release_snapshot
from modules.agent.application.use_cases.ai_release_cases import DeleteReleaseUseCase
from modules.agent.application.use_cases.ask_agent_stream_service import AskAgentStreamService
from modules.agent.application.use_cases.auto_compatible_release_lifecycle import AutoCompatibleReleaseLifecycleUseCase, _execution_snapshot_equal
from modules.agent.application.use_cases.execution_context import current_execution, new_execution_context
from modules.agent.application.use_cases.knowledge_release_validator import SafeDeleteDocumentUseCase
from modules.agent.application.use_cases.release_runtime_resolver import ReleaseRuntimeResolver
from modules.agent.application.use_cases.structured_output_ask_use_case import StructuredOutputAskAgentUseCase
from modules.agent.domain.entities import AgentRelease, Tool
from modules.agent.domain.enums import ReleaseStatus, RiskLevel, ToolStatus, ToolType
from shared.infra.errors import ConflictError


class MemoryReleaseRepository:
    def __init__(self, *items):
        self.items = {item.id: item for item in items}

    async def get_by_id(self, item_id):
        return self.items.get(item_id)

    async def save(self, item):
        self.items[item.id] = item
        return item

    async def list_by_status(self, agent_id, status):
        value = status.value if hasattr(status, "value") else status
        return [item for item in self.items.values() if item.agent_id == agent_id and getattr(item.status, "value", item.status) == value]

    async def list_by_agent(self, agent_id):
        return [item for item in self.items.values() if item.agent_id == agent_id]

    async def delete(self, item_id):
        self.items.pop(item_id, None)


def _release(*, status=ReleaseStatus.draft, version="draft", provider_model_id=None, runtime_config=None, knowledge_version_id=None):
    return AgentRelease(
        project_id=uuid4(),
        agent_id=uuid4(),
        version=version,
        status=status,
        provider_model_id=provider_model_id,
        provider="openai",
        model="model-a",
        runtime_config=runtime_config,
        knowledge_version_id=knowledge_version_id,
    )


def _tool():
    return Tool(
        project_id=uuid4(),
        name="Lookup",
        type=ToolType.HTTP,
        config={"url": "https://example.test/lookup", "method": "GET"},
        input_schema={"type": "object"},
        risk_level=RiskLevel.LOW,
        status=ToolStatus.ACTIVE,
    )


def test_release_equality_detects_provider_binding_change():
    left = _release(provider_model_id=uuid4())
    right = AgentRelease(**left.__dict__)
    right.provider_model_id = uuid4()
    assert not _execution_snapshot_equal(left, right)


@pytest.mark.asyncio
async def test_identical_production_does_not_mutate_release_notes():
    production = _release(status=ReleaseStatus.production, version="1.0.0")
    staging = AgentRelease(**production.__dict__)
    staging.id = uuid4()
    staging.status = ReleaseStatus.staging
    staging.version = "staging"
    repo = MemoryReleaseRepository(production, staging)
    result = await AutoCompatibleReleaseLifecycleUseCase(repo).execute(
        staging.agent_id,
        staging.id,
        SimpleNamespace(release_notes="new notes"),
        target_status="production",
    )
    assert result.id == production.id
    assert production.release_notes is None


@pytest.mark.asyncio
async def test_draft_staging_production_and_rollback_preserve_knowledge_and_tools():
    knowledge_id = uuid4()
    runtime = {"tools": {"tool_ids": [str(uuid4())], "snapshots": [{"snapshot_hash": "hash-a"}]}}
    draft = _release(runtime_config=runtime, knowledge_version_id=knowledge_id)
    repo = MemoryReleaseRepository(draft)
    lifecycle = AutoCompatibleReleaseLifecycleUseCase(repo)

    staging = await lifecycle.execute(draft.agent_id, draft.id, target_status="staging")
    production_v1 = await lifecycle.execute(staging.agent_id, staging.id, target_status="production")
    assert production_v1.knowledge_version_id == knowledge_id
    assert production_v1.runtime_config == runtime

    staging.runtime_config = {"tools": {"tool_ids": [], "snapshots": []}}
    staging.knowledge_version_id = uuid4()
    await repo.save(staging)
    production_v2 = await lifecycle.execute(staging.agent_id, staging.id, target_status="production")
    assert production_v2.id != production_v1.id

    restored = await lifecycle.execute(production_v1.agent_id, production_v1.id, target_status="production")
    assert restored.id == production_v1.id
    assert restored.knowledge_version_id == knowledge_id
    assert restored.runtime_config == runtime


@pytest.mark.asyncio
async def test_published_release_cannot_be_deleted():
    release = _release(status=ReleaseStatus.production, version="1.0.0")
    repo = MemoryReleaseRepository(release)
    with pytest.raises(ConflictError, match="immutable"):
        await DeleteReleaseUseCase(repo).execute(release.id)


def test_release_identity_is_bound_to_execution_context():
    release = _release(status=ReleaseStatus.staging, version="staging")
    token = current_execution.set(new_execution_context())
    try:
        ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)._bind_release_context(release)
        context = current_execution.get()
        assert context.agent_release_id == release.id
        assert context.agent_release_version == "staging"
    finally:
        current_execution.reset(token)


@pytest.mark.asyncio
async def test_document_delete_is_blocked_while_vector_build_is_active(monkeypatch):
    document = SimpleNamespace(id=uuid4(), project_id=uuid4(), collection_id=uuid4(), status="READY")
    doc_repo = SimpleNamespace(_session_or_uow=object(), get_by_id=AsyncMock(return_value=document))
    snapshot_repo = SimpleNamespace(get_active_building_by_collection=AsyncMock(return_value=object()))
    monkeypatch.setattr(
        "modules.agent.infra.database.vector_snapshot_repositories.SQLAlchemyVectorSnapshotRepository",
        lambda _session: snapshot_repo,
    )
    use_case = SafeDeleteDocumentUseCase(doc_repo, AsyncMock(), AsyncMock())
    with pytest.raises(ConflictError, match="building"):
        await use_case.execute(document.id)


def test_provider_model_references_are_registered_in_orm_metadata():
    from modules.agent.infra.database import provider_model_repositories  # noqa: F401
    from modules.agent.infra.database.models import AgentModel, AgentReleaseModel

    assert "provider_model_id" in AgentModel.__table__.c
    assert "fallback_provider_model_id" in AgentModel.__table__.c
    assert "provider_model_id" in AgentReleaseModel.__table__.c
    assert "fallback_provider_model_id" in AgentReleaseModel.__table__.c


@pytest.mark.asyncio
async def test_sources_are_persisted_with_assistant_message():
    from modules.agent.application.dtos.runtime_dtos import SourceInfo

    message_repo = SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(id=uuid4())))
    session_repo = SimpleNamespace(update=AsyncMock())
    outbox = SimpleNamespace(write=AsyncMock())
    session = SimpleNamespace(id=uuid4(), project_id=uuid4(), agent_id=uuid4(), last_message_at=None)
    usage = SimpleNamespace(input_tokens=1, output_tokens=2, cost_usd=0)
    context = new_execution_context()
    context.persisted_sources = [SourceInfo(document_id="doc-1", score=0.9)]
    token = current_execution.set(context)
    try:
        use_case = StructuredOutputAskAgentUseCase.__new__(StructuredOutputAskAgentUseCase)
        await use_case._do_save_assistant_message(message_repo, session_repo, outbox, session, "answer", usage, SimpleNamespace(id=session.agent_id), [])
    finally:
        current_execution.reset(token)
    saved_message = message_repo.create.await_args.args[0]
    assert saved_message.data["sources"][0]["document_id"] == "doc-1"


@pytest.mark.asyncio
async def test_streaming_executes_release_tool_snapshot(monkeypatch):
    tool = _tool()
    snapshot = tool_to_release_snapshot(tool)
    context = new_execution_context()
    context.tool_snapshots = {str(tool.id): snapshot}
    token = current_execution.set(context)

    result = SimpleNamespace(success=True, output={"ok": True}, duration_ms=3, error=None)
    registry = SimpleNamespace(execute=AsyncMock(return_value=result))
    fake_uow = SimpleNamespace(tool_secrets=object(), tools=object())

    class FakeContext:
        async def __aenter__(self):
            return fake_uow
        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr("modules.agent.application.use_cases.ask_agent_stream_service.AgentUnitOfWork", lambda _factory: FakeContext())
    monkeypatch.setattr("modules.agent.application.use_cases.ask_agent_stream_service.ToolSecretResolverAdapter", lambda *_args: object())
    monkeypatch.setattr("modules.agent.application.use_cases.ask_agent_stream_service.build_tool_runtime_registry", lambda **_kwargs: registry)

    service = AskAgentStreamService.__new__(AskAgentStreamService)
    service._session_factory = object()
    service._cipher = object()
    service._settings = object()
    service._http_executor = object()
    try:
        output = await service._execute_tool(tool.id, {})
    finally:
        current_execution.reset(token)

    executed_tool = registry.execute.await_args.args[0]
    assert executed_tool.config == tool.config
    assert output["success"] is True
