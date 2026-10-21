from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

import pytest
import httpx

from modules.agent.application.dtos.tools_dtos import McpToolConfig
from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
from modules.agent.application.tool_converter import agent_tool_to_openai_definition
from modules.agent.application.tool_runtime import MCP_AGENT_SESSION_INPUT_KEY, MCP_REMOTE_TOOL_INPUT_KEY
from modules.agent.domain.enums import ToolType
from modules.agent.infra.adapters.tool_runtime import McpToolRuntime
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.application.interfaces.ports import ExecutionResult, ToolExecutionPort
from shared.contracts.artifact_transfer import ArtifactTransferSource


INPUT_SCHEMA = {
    "type": "object",
    "properties": {"image": {"type": "string", "format": "byte"}},
    "required": ["image"],
}


@dataclass
class FakeTool:
    config: dict
    type: ToolType = ToolType.MCP
    id: object = uuid4()
    project_id: object = uuid4()
    timeout_ms: int = 30000
    input_schema: dict | None = None
    name: str = "mcp-image-tool"


class ScriptedExecutor(ToolExecutionPort):
    def __init__(self, results: list[ExecutionResult]) -> None:
        self.results = list(results)
        self.calls: list[dict] = []

    async def execute(self, method, url, headers=None, body=None, timeout_ms=30000):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "body": body})
        if not self.results:
            raise AssertionError("Unexpected MCP request")
        return self.results.pop(0)


class EventRecorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def emit(self, event_type, payload, *, durable=False):
        assert durable is True
        self.events.append((event_type, payload))


class SessionStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, session_id, ttl_seconds):
        del ttl_seconds
        self.values[key] = session_id

    async def delete(self, key):
        self.values.pop(key, None)


def _response(result=None, *, headers=None, success=True, status_code=200, error=None):
    return ExecutionResult(
        success=success,
        status_code=status_code,
        error=error,
        output={"headers": headers or {}, "body": {"result": result or {}}},
    )


def _config(mode="base64"):
    return {
        "protocol": "mcp",
        "mode": "tool",
        "server": {"transport": "streamable_http", "url": "https://mcp.example.test/mcp"},
        "tool_name": "inspect_image",
        "discovered_tools": [{"name": "inspect_image", "permission": {"mode": "allow"}}],
        "discovered_input_schema": INPUT_SCHEMA,
        "file_bindings": [{
            "input_name": "image",
            "mode": mode,
            "content_types": ["image/png"],
            "max_bytes": 64,
        }],
    }


def _executor(*, actual_schema=None, tool_result=None):
    return ScriptedExecutor([
        _response(headers={"mcp-session-id": "session-1"}),
        _response(),
        _response({"tools": [{"name": "inspect_image", "inputSchema": actual_schema or INPUT_SCHEMA}]}),
        _response(tool_result or {"content": [{"type": "text", "text": "done"}]}),
    ])


@pytest.mark.asyncio
async def test_mcp_base64_transfer_rechecks_schema_and_records_safe_receipts():
    raw = b"exact image bytes"
    reference = {"artifact_id": "art-1", "revision_id": "rev-7"}
    context = new_execution_context()
    context.run_id = uuid4()
    recorder = EventRecorder()
    context.run_event_recorder = recorder

    async def resolve(artifact_id, revision_id):
        assert (artifact_id, revision_id) == ("art-1", "rev-7")

        async def content():
            yield raw

        return ArtifactTransferSource(
            artifact_id=artifact_id,
            revision_id=revision_id,
            path="/private/image.png",
            content_type="image/png",
            size_bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            content=content(),
        )

    context.artifact_transfer_resolver = resolve
    executor = _executor()
    token = current_execution.set(context)
    try:
        result = await McpToolRuntime(executor).execute(
            FakeTool(config=_config()),
            {MCP_REMOTE_TOOL_INPUT_KEY: "inspect_image", "image": reference},
        )
    finally:
        current_execution.reset(token)

    assert result.success is True
    call = json.loads(executor.calls[-1]["body"])
    assert call["method"] == "tools/call"
    assert call["params"]["arguments"]["image"] == base64.b64encode(raw).decode("ascii")
    assert "/private/" not in str(call)
    assert [event for event, _payload in recorder.events] == [
        "artifact.transfer.started",
        "artifact.transfer.completed",
    ]
    assert recorder.events[-1][1]["input_refs"] == [reference]
    assert "content" not in str(recorder.events)
    assert result.output["artifact_transfer"]["state"] == "completed"


@pytest.mark.asyncio
async def test_mcp_schema_drift_fails_before_materializing_or_calling_tool():
    changed_schema = {
        "type": "object",
        "properties": {"image": {"type": "string", "format": "uri"}},
        "required": ["image"],
    }
    context = new_execution_context()
    context.run_id = uuid4()
    executor = _executor(actual_schema=changed_schema)
    token = current_execution.set(context)
    try:
        result = await McpToolRuntime(executor).execute(
            FakeTool(config=_config()),
            {MCP_REMOTE_TOOL_INPUT_KEY: "inspect_image", "image": {"artifact_id": "a", "revision_id": "r"}},
        )
    finally:
        current_execution.reset(token)
    assert result.success is False
    assert result.output["error_code"] == "MCP_ARTIFACT_SCHEMA_CHANGED"
    assert len(executor.calls) == 3
    assert json.loads(executor.calls[-1]["body"])["method"] == "tools/list"


@pytest.mark.asyncio
async def test_mcp_temporary_url_is_short_lived_and_scrubbed_from_results(monkeypatch):
    signed_url = "https://storage.example.test/object?X-Signature=canary"
    url_schema = {
        "type": "object",
        "properties": {"image": {"type": "string", "format": "uri"}},
        "required": ["image"],
    }
    config = _config(mode="url")
    config["discovered_input_schema"] = url_schema
    context = new_execution_context()
    context.run_id = uuid4()

    async def resolve(artifact_id, revision_id, destination_host):
        assert (artifact_id, revision_id) == ("art-1", "rev-7")
        assert destination_host == "mcp.example.test"
        return ArtifactTransferSource(
            artifact_id=artifact_id,
            revision_id=revision_id,
            path="image.png",
            content_type="image/png",
            size_bytes=20,
            sha256=hashlib.sha256(b"01234567890123456789").hexdigest(),
            temporary_url=signed_url,
            expires_in_seconds=60,
        )

    context.artifact_transfer_url_resolver = resolve
    monkeypatch.setattr(
        "modules.agent.infra.adapters.tool_executor._validated_public_addresses",
        lambda _url: frozenset({"8.8.8.8"}),
    )
    executor = _executor(
        actual_schema=url_schema,
        tool_result={"content": [{"type": "text", "text": f"received {signed_url}"}]},
    )
    token = current_execution.set(context)
    try:
        result = await McpToolRuntime(executor).execute(
            FakeTool(config=config),
            {MCP_REMOTE_TOOL_INPUT_KEY: "inspect_image", "image": {"artifact_id": "art-1", "revision_id": "rev-7"}},
        )
    finally:
        current_execution.reset(token)

    assert result.success is True
    call = json.loads(executor.calls[-1]["body"])
    assert call["params"]["arguments"]["image"] == signed_url
    assert signed_url not in str(result.output)


@pytest.mark.asyncio
async def test_mcp_temporary_url_requires_https_and_bounded_expiry():
    from modules.agent.infra.adapters.mcp_artifact_transfer import prepare_mcp_artifact_transfer

    async def resolve(_artifact_id, _revision_id, _host):
        return ArtifactTransferSource(
            artifact_id="art-1",
            revision_id="rev-7",
            path="image.png",
            content_type="image/png",
            size_bytes=1,
            sha256=hashlib.sha256(b"x").hexdigest(),
            temporary_url="http://storage.example.test/object?signature=bad",
            expires_in_seconds=60,
        )

    with pytest.raises(ValueError, match="HTTPS"):
        await prepare_mcp_artifact_transfer(
            _config(mode="url"),
            {"image": {"artifact_id": "art-1", "revision_id": "rev-7"}},
            server_url="https://mcp.example.test/mcp",
            transfer_resolver=None,
            url_resolver=resolve,
            run_id="run-1",
            tool_id="tool-1",
        )


@pytest.mark.asyncio
async def test_mcp_artifact_transfer_runs_through_the_http_peer_transport():
    raw = b"peer-upload"
    schema = INPUT_SCHEMA
    context = new_execution_context()
    context.run_id = uuid4()
    seen: list[dict] = []

    async def resolve(artifact_id, revision_id):
        async def content():
            yield raw

        return ArtifactTransferSource(
            artifact_id=artifact_id,
            revision_id=revision_id,
            path="peer.png",
            content_type="image/png",
            size_bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            content=content(),
        )

    context.artifact_transfer_resolver = resolve

    async def peer(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else {}
        method = payload.get("method")
        seen.append(payload)
        if method == "initialize":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": payload["id"], "result": {"capabilities": {}}},
                headers={"Mcp-Session-Id": "real-peer-session"},
                request=request,
            )
        if method == "notifications/initialized":
            return httpx.Response(202, request=request)
        if method == "tools/list":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": payload["id"], "result": {
                    "tools": [{"name": "inspect_image", "inputSchema": schema}],
                }},
                request=request,
            )
        if method == "tools/call":
            encoded = payload["params"]["arguments"]["image"]
            assert base64.b64decode(encoded) == raw
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": payload["id"], "result": {
                    "content": [{"type": "text", "text": "accepted"}],
                }},
                request=request,
            )
        raise AssertionError(f"unexpected method: {method}")

    config = _config()
    config["server"]["url"] = "http://127.0.0.1:8080/mcp"
    target = FakeTool(config=config)
    token = current_execution.set(context)
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(peer)) as client:
            runtime = McpToolRuntime(HttpToolExecutor(client=client, allow_local_networks=True))
            result = await runtime.execute(
                target,
                {MCP_REMOTE_TOOL_INPUT_KEY: "inspect_image", "image": {"artifact_id": "art-1", "revision_id": "rev-7"}},
            )
    finally:
        current_execution.reset(token)

    assert result.success is True
    assert [call["method"] for call in seen] == [
        "initialize", "notifications/initialized", "tools/list", "tools/call"
    ]


@pytest.mark.asyncio
async def test_mcp_session_cache_isolated_by_accepted_run_configuration():
    tool = FakeTool(config={
        "server": {"transport": "streamable_http", "url": "https://mcp.example.test/mcp"},
        "tool_name": "search",
        "authentication": {"type": "bearer", "fields": {
            "token": {"source": "project_environment", "key": "MCP_TOKEN"},
        }},
    })
    store = SessionStore()
    executor = ScriptedExecutor([
        _response(headers={"mcp-session-id": "session-run-1"}), _response(), _response(),
        _response(headers={"mcp-session-id": "session-run-2"}), _response(), _response(),
    ])
    runtime = McpToolRuntime(executor, session_store=store)
    for _ in range(2):
        context = new_execution_context()
        context.run_id = uuid4()
        context.project_id = tool.project_id
        token = current_execution.set(context)
        try:
            result = await runtime.execute(tool, {
                MCP_AGENT_SESSION_INPUT_KEY: "shared-agent-session",
                MCP_REMOTE_TOOL_INPUT_KEY: "search",
            })
        finally:
            current_execution.reset(token)
        assert result.success is True

    assert len(store.values) == 2
    assert all(":configuration:" in key for key in store.values)


@pytest.mark.asyncio
async def test_mcp_binary_resource_output_is_persisted_with_remote_operation_lineage():
    raw = b"generated from remote operation"
    encoded = base64.b64encode(raw).decode()
    config = _config()
    config.pop("file_bindings")
    config["output_bindings"] = [{
        "name": "generated_image",
        "mode": "mcp_resource",
        "path": "generated/output.png",
        "content_types": ["image/png"],
        "max_bytes": 1024,
        "resource_name": "generated-image",
        "operation_ref_pointer": "/operation_ref",
    }]
    executor = ScriptedExecutor([
        _response(headers={"mcp-session-id": "session-1"}),
        _response(),
        _response({
            "content": [{
                "type": "resource_link",
                "name": "generated-image",
                "uri": "mcp://documents/generated-1",
            }],
            "structuredContent": {"operation_ref": "provider-job-44"},
        }),
        _response({"contents": [{
            "uri": "mcp://documents/generated-1",
            "mimeType": "image/png",
            "blob": encoded,
        }]}),
    ])
    context = new_execution_context()
    context.run_id = uuid4()
    ingested = []

    async def ingest(**kwargs):
        ingested.append(kwargs)
        return {
            "artifact_id": "mcp-output",
            "revision_id": "mcp-revision",
            "path": kwargs["path"],
            "content_type": kwargs["content_type"],
            "size_bytes": len(kwargs["content"]),
            "sha256": hashlib.sha256(kwargs["content"]).hexdigest(),
            "source_refs": kwargs["source_refs"],
        }

    context.external_output_ingestor = ingest
    token = current_execution.set(context)
    try:
        result = await McpToolRuntime(executor).execute(
            FakeTool(config=config),
            {MCP_REMOTE_TOOL_INPUT_KEY: "inspect_image"},
        )
    finally:
        current_execution.reset(token)

    assert result.success is True
    assert len(executor.calls) == 4
    assert json.loads(executor.calls[-1]["body"])["method"] == "resources/read"
    assert ingested[0]["content"] == raw
    assert ingested[0]["content_type"] == "image/png"
    assert ingested[0]["external_operation_ref"] == "provider-job-44"
    assert result.output["output_artifacts"][0]["revision_id"] == "mcp-revision"
    assert encoded not in str(result.output)
    assert "uri" not in result.output["mcp"]["content"][0]


@pytest.mark.asyncio
async def test_mcp_resource_links_are_read_through_same_peer_and_bounded_as_text():
    tool_result = {
        "content": [
            {"type": "resource_link", "name": "external", "uri": "file:///etc/passwd"},
            {"type": "resource_link", "name": "result", "uri": "mcp://documents/result-1"},
            {"type": "text", "text": "complete"},
        ],
        "structuredContent": {"answer": "complete", "data": "structured field"},
    }
    executor = ScriptedExecutor([
        _response(headers={"mcp-session-id": "session-1"}),
        _response(),
        _response(tool_result),
        _response({"contents": [{"uri": "mcp://documents/result-1", "mimeType": "text/plain", "text": "x" * 70000}]}),
    ])
    config = _config()
    config.pop("file_bindings")
    result = await McpToolRuntime(executor).test(
        config,
        {MCP_REMOTE_TOOL_INPUT_KEY: "inspect_image"},
    )
    assert result.success is True
    assert len(executor.calls) == 4
    resource_read = json.loads(executor.calls[-1]["body"])
    assert resource_read["method"] == "resources/read"
    assert resource_read["params"] == {"uri": "mcp://documents/result-1"}
    content = result.output["mcp"]["content"]
    assert content[0]["text"] == "[MCP resource omitted: invalid or over limit]"
    assert len(content[1]["text"]) == 65536
    assert content[1]["name"] == "result"
    assert "uri" not in content[1]
    assert result.output["mcp"]["structuredContent"]["data"] == "structured field"


@pytest.mark.asyncio
async def test_mcp_is_error_result_remains_a_failed_tool_call():
    executor = ScriptedExecutor([
        _response(headers={"mcp-session-id": "session-1"}),
        _response(),
        _response({"isError": True, "content": [{"type": "text", "text": "provider rejected input"}]}),
    ])
    config = _config()
    config.pop("file_bindings")
    result = await McpToolRuntime(executor).test(
        config,
        {MCP_REMOTE_TOOL_INPUT_KEY: "inspect_image"},
    )
    assert result.success is False
    assert result.output["error_code"] == "MCP_TOOL_ERROR"
    assert len(executor.calls) == 3


def test_mcp_file_binding_requires_schema_compatible_encoding_and_exposes_artifact_ref():
    valid = McpToolConfig(
        server={"url": "https://mcp.example.test/mcp"},
        tool_name="inspect_image",
        discovered_input_schema=INPUT_SCHEMA,
        file_bindings=[{"input_name": "image", "mode": "base64", "content_types": ["image/png"]}],
    )
    assert valid.file_bindings[0].mode == "base64"
    with pytest.raises(ValueError, match="does not match"):
        McpToolConfig(
            server={"url": "https://mcp.example.test/mcp"},
            tool_name="inspect_image",
            discovered_input_schema=INPUT_SCHEMA,
            file_bindings=[{"input_name": "image", "mode": "url", "content_types": ["image/png"]}],
        )

    tool = SimpleNamespace(
        id=uuid4(),
        type=ToolType.MCP,
        name="inspect-image",
        description=None,
        input_schema=None,
        config=_config(),
    )
    parameters = agent_tool_to_openai_definition(tool)["function"]["parameters"]
    assert parameters["properties"]["image"]["type"] == "object"
    assert parameters["properties"]["image"]["required"] == ["artifact_id", "revision_id"]

