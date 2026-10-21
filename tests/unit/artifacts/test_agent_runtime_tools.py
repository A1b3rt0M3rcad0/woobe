from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID

import pytest
from langchain_core.messages import AIMessage

from modules.agent.infra.execution.ask_use_case import AskAgentUseCase
from modules.artifacts.domain.models import Action, ArtifactError, Environment, Scope
from shared.composition.artifact_agent_tools import build_runtime_artifact_tools


@dataclass
class _Receipt:
    artifact_id: str
    revision_id: str


class _Page:
    def __init__(self, items=(), *, has_more=False, next_cursor=None):
        self.items = items
        self.has_more = has_more
        self.next_cursor = next_cursor

    def model_dump(self, *, mode):
        assert mode == "json"
        return {"items": [], "has_more": False, "next_cursor": None}


class _FakeModel:
    def __init__(self):
        self.responses = [
            AIMessage(content="", tool_calls=[{
                "id": "search-1", "name": "woobe_artifact_search",
                "args": {"query": "Chapter 4", "limit": 3}, "type": "tool_call",
            }]),
            AIMessage(content="", tool_calls=[{
                "id": "read-1", "name": "woobe_artifact_read",
                "args": {"source": {
                    "artifact_id": "chapter-4", "revision_id": "revision-4",
                    "source_sha256": "a" * 64,
                }, "max_chars": 512}, "type": "tool_call",
            }]),
            AIMessage(content="", tool_calls=[{
                "id": "write-1", "name": "woobe_artifact_write",
                "args": {"path": "summaries/chapter-4.txt", "text": "Chapter summary."},
                "type": "tool_call",
            }]),
            AIMessage(content="Summary written."),
        ]
        self.index = 0
        self.definitions = None

    def bind_tools(self, definitions, *, tool_choice):
        assert tool_choice == "auto"
        self.definitions = definitions
        return self

    async def ainvoke(self, _messages):
        result = self.responses[self.index]
        self.index += 1
        return result


class _Factory:
    def __init__(self, model):
        self.model = model

    def create_chat_model(self, **_kwargs):
        return self.model


def _binding(actions):
    return SimpleNamespace(
        workspace_id="bound-workspace",
        scope=Scope("project-1", Environment.DRAFT),
        catalog_version=7,
        actions=frozenset(actions),
    )


@pytest.mark.asyncio
async def test_deterministic_agent_finds_reads_and_writes_through_bound_tools(monkeypatch):
    from modules.artifacts.composition.composers import (
        get_file, get_document_index, list_document_nodes, list_files,
        search_documents,
    )
    from modules.artifacts.composition import files as files_composition
    from modules.artifacts.composition import representations as representations_composition

    observed = []

    async def search(request):
        observed.append(("search", request.workspace_id, request.query, request.run_id))
        return _Page()

    class FileService:
        async def write_text(self, request):
            observed.append(("write", request.workspace_id, request.run_id,
                             request.node_id, request.operation_id))
            return SimpleNamespace(receipt=_Receipt("summary-4", "summary-rev-1"))

    async def read_source(request):
        observed.append(("read", request.workspace_id, request.run_id,
                         request.definition.source.artifact_id))
        return SimpleNamespace(model_dump=lambda *, mode: {
            "text": "Chapter 4 source", "source": {
                "artifact_id": "chapter-4", "revision_id": "revision-4",
            }, "offset": 0, "next_offset": None, "truncated": False,
        })

    async def unused(*_args, **_kwargs):
        raise AssertionError("The deterministic model did not request this capability")

    monkeypatch.setattr(list_files, "list_files_composer", lambda: unused)
    monkeypatch.setattr(get_file, "get_file_composer", lambda: unused)
    monkeypatch.setattr(get_document_index, "get_document_index_composer", lambda: unused)
    monkeypatch.setattr(list_document_nodes, "list_document_nodes_composer", lambda: unused)
    monkeypatch.setattr(search_documents, "search_documents_composer", lambda: search)
    monkeypatch.setattr(files_composition, "build_file_service", FileService)
    monkeypatch.setattr(
        representations_composition, "build_representation_service",
        lambda: SimpleNamespace(read_source=read_source),
    )

    principal = SimpleNamespace(user_id="user-1")
    definitions, names, handlers = build_runtime_artifact_tools(
        principal=principal, binding=_binding({Action.READ, Action.SEARCH, Action.WRITE}),
        run_id="run-1", node_id="node-1",
    )
    model = _FakeModel()

    async def execute_tool(tool_id: UUID, args: dict):
        return await handlers[tool_id](args)

    use_case = AskAgentUseCase(
        transactions=SimpleNamespace(), llm_factory=_Factory(model),
        tool_executor_factory=execute_tool,
    )
    result, calls, was_called, _ = await use_case._execute_llm(
        agent=SimpleNamespace(provider="custom", model="deterministic", temperature=0,
                              max_output_tokens=300),
        api_key="test", base_url=None, response_format={}, json_enabled=False,
        has_tools=True, agent_tools=definitions,
        tool_name_to_id=names, messages=[],
    )

    assert result.content == "Summary written."
    assert was_called is True
    assert [call.tool_name for call in calls] == [
        "woobe_artifact_search", "woobe_artifact_read", "woobe_artifact_write",
    ]
    assert all(call.success for call in calls)
    assert [entry[0] for entry in observed] == ["search", "read", "write"]
    assert all(entry[1] == "bound-workspace" for entry in observed)
    assert observed[0][3] == "run-1"
    assert observed[-1][2:4] == ("run-1", "node-1")
    assert len({item["function"]["name"] for item in model.definitions}) == 6
    assert all("workspace_id" not in str(item["function"]["parameters"])
               for item in model.definitions)


@pytest.mark.asyncio
async def test_tool_inventory_is_limited_by_effective_actions_and_write_reuses_receipt(monkeypatch):
    from modules.artifacts.composition import files as files_composition

    writes = []

    class FileService:
        async def write_text(self, request):
            writes.append(request)
            return SimpleNamespace(receipt=_Receipt("summary", "revision"))

    monkeypatch.setattr(files_composition, "build_file_service", FileService)
    principal = SimpleNamespace(user_id="user-1")
    definitions, names, handlers = build_runtime_artifact_tools(
        principal=principal, binding=_binding({Action.WRITE}), run_id="run-1",
    )
    assert [item["function"]["name"] for item in definitions] == ["woobe_artifact_write"]
    assert set(names) == {"woobe_artifact_write"}

    handler = handlers[UUID(names["woobe_artifact_write"])]
    args = {"path": "summary.txt", "text": "Same content"}
    first = await handler(args)
    second = await handler(args)
    assert first == second
    assert writes[0].operation_id == writes[1].operation_id


@pytest.mark.asyncio
async def test_internal_handler_rejects_scope_arguments_and_process_failure_is_not_success(monkeypatch):
    from modules.artifacts.composition.composers import (
        get_file, get_document_index, list_document_nodes, list_files,
        request_processing, search_documents,
    )
    from modules.artifacts.composition import files as files_composition
    from modules.artifacts.composition import representations as representations_composition

    async def unused(*_args, **_kwargs):
        raise AssertionError("Unexpected tool execution")

    async def fail_processing(_request):
        raise RuntimeError("processor is unavailable")

    monkeypatch.setattr(list_files, "list_files_composer", lambda: unused)
    monkeypatch.setattr(get_file, "get_file_composer", lambda: unused)
    monkeypatch.setattr(get_document_index, "get_document_index_composer", lambda: unused)
    monkeypatch.setattr(list_document_nodes, "list_document_nodes_composer", lambda: unused)
    monkeypatch.setattr(search_documents, "search_documents_composer", lambda: unused)
    monkeypatch.setattr(request_processing, "request_processing_composer", lambda: fail_processing)
    monkeypatch.setattr(files_composition, "build_file_service", lambda: unused)
    monkeypatch.setattr(representations_composition, "build_representation_service", lambda: SimpleNamespace(read_source=unused))

    definitions, names, handlers = build_runtime_artifact_tools(
        principal=SimpleNamespace(user_id="user-1"),
        binding=_binding({Action.READ, Action.PROCESS}), run_id="run-1",
    )
    list_handler = handlers[UUID(names["woobe_artifact_list"])]
    with pytest.raises(ValueError):
        await list_handler({"workspace_id": "attacker-workspace"})

    process_id = UUID(names["woobe_artifact_process"])
    use_case = AskAgentUseCase(transactions=SimpleNamespace())
    use_case._tool_executor_factory = lambda tool_id, args: handlers[tool_id](args)
    failed = await use_case._execute_single_tool(
        {"args": {"artifact_id": "artifact-1", "revision_id": "revision-1"}},
        str(process_id),
    )
    assert failed["success"] is False
    assert "processor is unavailable" in failed["error"]

    hidden = await use_case._execute_single_tool(
        {"args": {}}, "woobe_artifact_unlisted",
    )
    assert hidden["success"] is False


@pytest.mark.asyncio
async def test_artifact_read_budget_is_shared_and_identical_source_reads_are_cached(monkeypatch):
    from modules.artifacts.composition.composers import (
        get_document_index, get_file, list_document_nodes, list_files,
    )
    from modules.artifacts.composition import representations as representations_composition

    source_reads = []

    async def unused(*_args, **_kwargs):
        raise AssertionError("Unexpected operation")

    async def read_source(request):
        source_reads.append(request)
        return SimpleNamespace(model_dump=lambda *, mode: {
            "text": "x" * request.definition.max_chars,
            "source": request.definition.source.model_dump(mode="json"),
            "offset": request.definition.offset,
            "next_offset": None,
            "truncated": False,
        })

    monkeypatch.setattr(list_files, "list_files_composer", lambda: unused)
    monkeypatch.setattr(get_file, "get_file_composer", lambda: unused)
    monkeypatch.setattr(get_document_index, "get_document_index_composer", lambda: unused)
    monkeypatch.setattr(list_document_nodes, "list_document_nodes_composer", lambda: unused)
    monkeypatch.setattr(
        representations_composition, "build_representation_service",
        lambda: SimpleNamespace(read_source=read_source),
    )

    budget = {"calls": 0, "read_bytes": 65_532}
    definitions, names, handlers = build_runtime_artifact_tools(
        principal=SimpleNamespace(user_id="user-1"),
        binding=_binding({Action.READ}), run_id="run-1", budget=budget,
    )
    assert [item["function"]["name"] for item in definitions] == [
        "woobe_artifact_list", "woobe_artifact_inspect",
        "woobe_artifact_outline", "woobe_artifact_read",
    ]
    handler = handlers[UUID(names["woobe_artifact_read"])]
    args = {"source": {
        "artifact_id": "chapter-4", "revision_id": "revision-4",
        "source_sha256": "a" * 64,
    }, "max_chars": 8192}
    first = await handler(args)
    second = await handler(args)
    assert first == second
    assert len(source_reads) == 1
    assert source_reads[0].definition.max_chars == 1
    assert budget == {"calls": 2, "read_bytes": 65_533}

    with pytest.raises(ArtifactError, match="per-Run 64 KiB budget"):
        await handler({**args, "offset": 1})


def test_artifact_tool_result_metadata_marks_document_text_untrusted():
    from modules.agent.application.interfaces.tool_result_context import (
        tool_result_context_metadata,
    )

    metadata = tool_result_context_metadata(
        tool_name="woobe_artifact_read", tool_call_id="call-1",
    )
    assert metadata["woobe_context"]["source_type"] == "ARTIFACT"
    assert metadata["woobe_context"]["trust"] == "untrusted_document"
