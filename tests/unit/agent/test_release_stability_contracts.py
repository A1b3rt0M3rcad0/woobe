from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.tool_release_snapshots import tool_to_release_snapshot
from modules.agent.application.use_cases.ai_release_cases import DeleteReleaseUseCase
from modules.agent.runtime.agent_tool_runtime_gateway import AgentToolRuntimeGateway
from modules.agent.application.use_cases.auto_compatible_release_lifecycle import AutoCompatibleReleaseLifecycleUseCase, _execution_snapshot_equal
from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
from modules.agent.application.use_cases.knowledge_release_validator import SafeDeleteDocumentUseCase
from modules.agent.runtime.release_runtime_resolver import ReleaseRuntimeResolver
from modules.agent.runtime.session_continuity_runtime_resolver import SessionContinuityReleaseRuntimeResolver
from modules.agent.runtime.structured_output_ask_use_case import StructuredOutputAskAgentUseCase
from modules.agent.domain.entities import Agent, AgentRelease, Tool
from modules.agent.domain.enums import ReleaseStatus, RiskLevel, ToolStatus, ToolType
from shared.infra.errors import ConflictError


class MemoryReleaseRepository:
    def __init__(self, *items):
        self.items = {item.id: item for item in items}

    async def get_by_id(self, item_id):
        return self.items.get(item_id)

    async def get_active_production(self, agent_id):
        return next(
            (
                item
                for item in self.items.values()
                if item.agent_id == agent_id and item.status == ReleaseStatus.production
            ),
            None,
        )

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


def _runtime(*, top_k=5, tool_ids=None, snapshots=None):
    rag = RAGRuntimeConfig(top_k=top_k, max_context_chunks=min(5, top_k)).model_dump()
    return {
        "rag": rag,
        "tools": {
            "tool_ids": tool_ids or [],
            "snapshots": snapshots or [],
        },
    }


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
    production.snapshot_kind = "release"
    staging.snapshot_kind = "staging"
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
async def test_draft_staging_production_and_rollback_preserve_knowledge_tools_and_rag():
    knowledge_v1 = uuid4()
    tool_v1 = str(uuid4())
    runtime_v1 = _runtime(
        top_k=5,
        tool_ids=[tool_v1],
        snapshots=[{"snapshot_hash": "hash-a"}],
    )
    draft = _release(runtime_config=runtime_v1, knowledge_version_id=knowledge_v1)
    repo = MemoryReleaseRepository(draft)
    lifecycle = AutoCompatibleReleaseLifecycleUseCase(repo)

    staging_v1 = await lifecycle.execute(draft.agent_id, draft.id, target_status="staging")
    assert staging_v1.runtime_config == runtime_v1

    knowledge_v2 = uuid4()
    runtime_v2 = _runtime(top_k=8, tool_ids=[str(uuid4())])
    draft.runtime_config = runtime_v2
    draft.knowledge_version_id = knowledge_v2
    await repo.save(draft)

    stored_staging_v1 = await repo.get_by_id(staging_v1.id)
    assert stored_staging_v1.runtime_config == runtime_v1
    assert stored_staging_v1.knowledge_version_id == knowledge_v1

    staging_v2 = await lifecycle.execute(draft.agent_id, draft.id, target_status="staging")
    assert staging_v2.runtime_config == runtime_v2
    assert staging_v2.knowledge_version_id == knowledge_v2

    production_v1 = await lifecycle.execute(staging_v2.agent_id, staging_v2.id, target_status="production")
    assert production_v1.runtime_config == runtime_v2
    assert production_v1.knowledge_version_id == knowledge_v2

    runtime_v3 = _runtime(top_k=10, tool_ids=[str(uuid4())])
    draft.runtime_config = runtime_v3
    draft.knowledge_version_id = uuid4()
    await repo.save(draft)
    staging_v3 = await lifecycle.execute(draft.agent_id, draft.id, target_status="staging")
    production_v2 = await lifecycle.execute(staging_v3.agent_id, staging_v3.id, target_status="production")
    assert production_v2.id != production_v1.id
    assert production_v2.runtime_config == runtime_v3

    restored = await lifecycle.execute(production_v1.agent_id, production_v1.id, target_status="production")
    assert restored.id == production_v1.id
    assert restored.knowledge_version_id == knowledge_v2
    assert restored.runtime_config == runtime_v2


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
async def test_staging_session_follows_current_staging_release_after_staging_moves():
    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    base_agent = Agent(id=agent_id, project_id=project_id, model="draft-model")
    opened = _release(status=ReleaseStatus.released, version="staging-v1")
    opened.project_id = project_id
    opened.agent_id = agent_id
    opened.model = "model-v1"
    current = _release(status=ReleaseStatus.staging, version="staging-v2")
    current.project_id = project_id
    current.agent_id = agent_id
    current.model = "model-v2"
    session = SimpleNamespace(
        project_id=project_id,
        agent_id=agent_id,
        runtime_environment="staging",
        opened_release_id=opened.id,
        data=None,
    )
    uow = SimpleNamespace(
        agents=SimpleNamespace(get_by_id=AsyncMock(return_value=base_agent)),
        releases=MemoryReleaseRepository(opened, current),
        sessions=SimpleNamespace(get_by_id=AsyncMock(return_value=session)),
        provider_models=None,
    )
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent_id,
        session_id=session_id,
        message="continue",
        execution_context="staging",
        loaded_release_id=opened.id,
    )

    loaded = await SessionContinuityReleaseRuntimeResolver.__new__(SessionContinuityReleaseRuntimeResolver)._load_agent(uow, input_dto)

    assert loaded.model == "model-v2"
    assert input_dto.loaded_release_id == current.id
    assert session.opened_release_id == opened.id


@pytest.mark.asyncio
async def test_session_cannot_cross_runtime_environments():
    project_id = uuid4()
    agent_id = uuid4()
    session = SimpleNamespace(
        project_id=project_id,
        agent_id=agent_id,
        runtime_environment="draft",
        opened_release_id=None,
        data=None,
    )
    uow = SimpleNamespace(sessions=SimpleNamespace(get_by_id=AsyncMock(return_value=session)))
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent_id,
        session_id=uuid4(),
        message="continue",
        execution_context="production",
    )

    with pytest.raises(ConflictError, match="belongs to draft"):
        await SessionContinuityReleaseRuntimeResolver.__new__(SessionContinuityReleaseRuntimeResolver)._session_runtime_binding(uow, input_dto)


@pytest.mark.asyncio
async def test_runtime_session_persists_environment_and_opening_release_provenance():
    project_id = uuid4()
    agent_id = uuid4()
    release_id = uuid4()
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent_id,
        message="hello",
        execution_context="staging",
        loaded_release_id=release_id,
        metadata={"source": "playground"},
    )
    agent = Agent(id=agent_id, project_id=project_id, model="model-a")
    created = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        agent_id=agent_id,
        runtime_environment="draft",
        opened_release_id=None,
        data=None,
    )
    session_repo = SimpleNamespace(
        create=AsyncMock(return_value=created),
        update=AsyncMock(),
    )
    context = new_execution_context()
    context.agent_release_id = release_id
    context.agent_release_version = "staging-v1"
    token = current_execution.set(context)
    try:
        session = await SessionContinuityReleaseRuntimeResolver.__new__(SessionContinuityReleaseRuntimeResolver)._resolve_session(
            session_repo,
            input_dto,
            agent,
        )
    finally:
        current_execution.reset(token)

    assert session.runtime_environment == "staging"
    assert session.opened_release_id == release_id
    assert session.data == {"source": "playground"}
    session_repo.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_document_delete_is_blocked_while_vector_build_is_active():
    document = SimpleNamespace(id=uuid4(), project_id=uuid4(), collection_id=uuid4(), status="READY")
    doc_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=document),
        has_active_vector_build=AsyncMock(return_value=True),
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
    fake_uow = SimpleNamespace()

    class FakeContext:
        async def __aenter__(self):
            return fake_uow

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(
        "modules.agent.runtime.agent_tool_runtime_gateway.AgentUnitOfWork",
        lambda _database: FakeContext(),
    )
    monkeypatch.setattr(
        "modules.agent.runtime.agent_tool_runtime_gateway.ToolSecretResolverAdapter",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        "modules.agent.runtime.agent_tool_runtime_gateway.build_tool_runtime_registry",
        lambda **_kwargs: registry,
    )

    gateway = AgentToolRuntimeGateway.__new__(AgentToolRuntimeGateway)
    gateway._database = object()
    gateway._cipher = object()
    gateway._settings = object()
    gateway._executor = object()
    try:
        output = await gateway.execute_tool(tool.id, {})
    finally:
        current_execution.reset(token)

    executed_tool = registry.execute.await_args.args[0]
    assert executed_tool.config == tool.config
    assert output["success"] is True