from __future__ import annotations

import base64
import hashlib
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
from modules.agent.application.interfaces.ports import ExecutionResult, ToolExecutionPort
from modules.agent.domain.enums import ToolType
from modules.agent.infra.adapters.external_artifact_output import (
    ExternalOutputError,
    _decode_binding,
    ingest_http_outputs,
    persist_external_output,
)
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.adapters.tool_runtime import HttpToolRuntime


class FakeExecutor(ToolExecutionPort):
    def __init__(self, result):
        self.result = result

    async def execute(self, method, url, headers=None, body=None, timeout_ms=30000):
        return self.result


def http_tool(config):
    return SimpleNamespace(
        id="tool-1",
        type=ToolType.HTTP,
        name="generate-file",
        description="Generate a file",
        project_id=uuid4(),
        timeout_ms=30000,
        input_schema={"type": "object", "properties": {}, "required": []},
        config=config,
    )


def output_binding(**overrides):
    return {
        "name": "generated",
        "mode": "json_base64",
        "path": "generated/result.md",
        "content_types": ["text/markdown"],
        "max_bytes": 1024,
        "data_pointer": "/file/data",
        **overrides,
    }


@pytest.mark.asyncio
async def test_http_json_output_is_verified_ingested_and_removed_from_model_payload():
    raw = b"# Generated\n"
    digest = hashlib.sha256(raw).hexdigest()
    payload = {"file": {
        "data": base64.b64encode(raw).decode(),
        "content_type": "text/markdown",
        "sha256": digest,
        "operation_ref": "provider-job-123",
    }}
    captured = []
    context = new_execution_context()
    context.run_id = uuid4()

    async def ingest(**kwargs):
        captured.append(kwargs)
        return {
            "artifact_id": "output-artifact",
            "revision_id": "output-revision",
            "path": kwargs["path"],
            "content_type": kwargs["content_type"],
            "size_bytes": len(kwargs["content"]),
            "sha256": hashlib.sha256(kwargs["content"]).hexdigest(),
            "source_refs": kwargs["source_refs"],
        }

    context.external_output_ingestor = ingest
    config = {
        "protocol": "http",
        "method": "POST",
        "url": "https://api.example.test/generate",
        "output_bindings": [output_binding(
            content_type_pointer="/file/content_type",
            sha256_pointer="/file/sha256",
            operation_ref_pointer="/file/operation_ref",
        )],
    }
    token = current_execution.set(context)
    try:
        result = await HttpToolRuntime(FakeExecutor(ExecutionResult(
            success=True,
            status_code=200,
            output={"body": payload, "headers": {"content-type": "application/json"}},
        ))).execute(http_tool(config), {})
    finally:
        current_execution.reset(token)

    assert result.success is True
    assert captured[0]["content"] == raw
    assert captured[0]["producer_id"] == "tool-1"
    assert captured[0]["external_operation_ref"] == "provider-job-123"
    assert result.output["output_artifacts"][0]["revision_id"] == "output-revision"
    assert result.output["body"] == {"artifact_outputs": ["output-artifact"]}
    assert base64.b64encode(raw).decode() not in str(result.output)
    assert result.response_content is None


@pytest.mark.asyncio
async def test_http_binary_response_uses_bounded_response_capture(monkeypatch):
    raw = b"external image bytes"
    captured = []
    context = new_execution_context()
    context.run_id = uuid4()

    async def ingest(**kwargs):
        captured.append(kwargs)
        return {
            "artifact_id": "image-artifact",
            "revision_id": "image-revision",
            "path": kwargs["path"],
            "content_type": kwargs["content_type"],
            "size_bytes": len(kwargs["content"]),
            "sha256": hashlib.sha256(kwargs["content"]).hexdigest(),
        }

    context.external_output_ingestor = ingest
    monkeypatch.setattr(
        "modules.agent.infra.adapters.tool_executor._validated_public_addresses",
        lambda _url: frozenset({"8.8.8.8"}),
    )

    async def peer(request):
        return httpx.Response(200, content=raw, headers={"content-type": "image/png"}, request=request)

    config = {
        "protocol": "http",
        "method": "GET",
        "url": "https://api.example.test/image",
        "output_bindings": [{
            "name": "image",
            "mode": "response_body",
            "path": "generated/image.png",
            "content_types": ["image/png"],
            "max_bytes": 1024,
        }],
    }
    token = current_execution.set(context)
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(peer)) as client:
            runtime = HttpToolRuntime(HttpToolExecutor(client=client))
            result = await runtime.execute(http_tool(config), {})
    finally:
        current_execution.reset(token)

    assert result.success is True
    assert captured[0]["content"] == raw
    assert captured[0]["content_type"] == "image/png"
    assert result.output["output_artifacts"][0]["artifact_id"] == "image-artifact"
    assert raw.decode() not in str(result.output)


@pytest.mark.asyncio
async def test_hash_mismatch_and_application_errors_never_publish_outputs():
    raw = b"untrusted result"
    payload = {"file": {
        "data": base64.b64encode(raw).decode(),
        "content_type": "text/markdown",
        "sha256": "0" * 64,
        "success": True,
    }}
    calls = []
    context = new_execution_context()
    context.run_id = uuid4()

    async def ingest(**kwargs):
        calls.append(kwargs)
        return {}

    context.external_output_ingestor = ingest
    config = {
        "protocol": "http",
        "method": "POST",
        "url": "https://api.example.test/generate",
        "output_bindings": [output_binding(
            content_type_pointer="/file/content_type",
            sha256_pointer="/file/sha256",
            success_pointer="/file/success",
        )],
    }
    token = current_execution.set(context)
    try:
        result = await HttpToolRuntime(FakeExecutor(ExecutionResult(
            success=True, status_code=200, output={"body": payload},
        ))).execute(http_tool(config), {})
    finally:
        current_execution.reset(token)
    assert result.success is False
    assert result.output["error_code"] == "UPLOAD_INTEGRITY_MISMATCH"
    assert calls == []

    binding = _decode_binding(output_binding(success_pointer="/file/success"), allowed_modes={"json_base64"})
    with pytest.raises(ExternalOutputError, match="application error"):
        await persist_external_output(
            binding=binding,
            source={"body": {"file": {"success": False}}},
            default_content_type="text/markdown",
            ingestor=ingest,
            run_id="run-1",
            tool_id="tool-1",
            source_refs=[],
        )


@pytest.mark.asyncio
async def test_repeated_ready_response_uses_stable_operation_identity():
    calls = []
    binding = _decode_binding(output_binding(
        operation_ref_pointer="/file/operation_id",
    ), allowed_modes={"json_base64"})

    async def ingest(**kwargs):
        calls.append(kwargs)
        return {"artifact_id": "artifact-1", "revision_id": "revision-1"}

    source = {"body": {"file": {
        "data": base64.b64encode(b"same result").decode(),
        "operation_id": "job-42",
    }}}
    for _ in range(2):
        await persist_external_output(
            binding=binding, source=source, default_content_type="text/markdown",
            ingestor=ingest, run_id="run-1", tool_id="tool-1", source_refs=[],
        )
    assert calls[0]["operation_id"] == calls[1]["operation_id"]
    assert calls[0]["external_operation_ref"] == calls[1]["external_operation_ref"] == "job-42"


@pytest.mark.asyncio
async def test_configured_polling_keeps_pending_result_and_replays_ready_idempotently():
    calls = []
    events = []
    context = new_execution_context()
    context.run_id = "run-1"
    async def emit(event_type, payload, *, durable=False):
        events.append((event_type, payload, durable))
    context.run_event_recorder = SimpleNamespace(emit=emit)

    async def ingest(**kwargs):
        calls.append(kwargs)
        return {"artifact_id": "artifact-1", "revision_id": "revision-1"}

    context.external_output_ingestor = ingest
    config = {"output_bindings": [output_binding(
        operation_ref_pointer="/file/operation_id",
        status_pointer="/file/status",
        content_type_pointer="/file/content_type",
        pending_statuses=["queued", "running"],
    )]}
    pending = ExecutionResult(success=True, status_code=202, output={"body": {"file": {
        "operation_id": "job-42", "status": "running",
    }}})
    result = await ingest_http_outputs(
        pending, config=config, input_data={}, transfer=None, context=context, tool_id="tool-1",
    )
    assert result.output["external_operations"] == [{
        "binding": "generated", "operation_ref": "job-42", "status": "running",
    }]
    assert calls == []
    assert events[0][0] == "artifact.external_operation.pending"
    assert events[0][1]["external_operation_ref"] == "job-42"
    assert events[0][2] is True

    def ready():
        return ExecutionResult(success=True, status_code=200, output={"body": {"file": {
            "operation_id": "job-42", "status": "ready",
            "content_type": "text/markdown",
            "data": base64.b64encode(b"final result").decode(),
        }}})
    for _ in range(2):
        await ingest_http_outputs(
            ready(), config=config, input_data={}, transfer=None, context=context, tool_id="tool-1",
        )
    assert calls[0]["operation_id"] == calls[1]["operation_id"]
    assert calls[0]["external_operation_ref"] == "job-42"


@pytest.mark.asyncio
async def test_late_external_result_after_run_terminalization_is_not_published():
    calls = []
    context = new_execution_context()
    context.run_id = "run-1"
    context.terminal_persisted = True

    async def ingest(**kwargs):
        calls.append(kwargs)
        return {"artifact_id": "artifact-1", "revision_id": "revision-1"}

    context.external_output_ingestor = ingest
    result = ExecutionResult(success=True, status_code=200, output={"body": {"file": {
        "data": base64.b64encode(b"late result").decode(),
    }}})
    with pytest.raises(ExternalOutputError, match="Run stopped accepting output"):
        await ingest_http_outputs(
            result, config={"output_bindings": [output_binding()]}, input_data={},
            transfer=None, context=context, tool_id="tool-1",
        )
    assert calls == []


@pytest.mark.asyncio
async def test_external_output_rejects_partial_payloads_and_never_fetches_urls():
    calls = []

    async def ingest(**kwargs):
        calls.append(kwargs)
        return {"artifact_id": "artifact-1", "revision_id": "revision-1"}

    binding = _decode_binding(output_binding(), allowed_modes={"json_base64"})
    for source in (
        {"body": {"file": {"data": "https://untrusted.example/file.md"}}},
        {"body": {"file": {}}},
    ):
        with pytest.raises(ExternalOutputError, match="base64 output is invalid|configured schema"):
            await persist_external_output(
                binding=binding, source=source, default_content_type="text/markdown",
                ingestor=ingest, run_id="run-1", tool_id="tool-1", source_refs=[],
            )
    assert calls == []


def test_output_binding_rejects_path_escape_and_protocol_mismatch():
    with pytest.raises(ExternalOutputError, match="binding is invalid"):
        _decode_binding(output_binding(path="../secret.md"), allowed_modes={"json_base64"})
    with pytest.raises(ExternalOutputError, match="incompatible"):
        _decode_binding(output_binding(mode="mcp_resource", data_pointer=None, resource_name="generated"), allowed_modes={"json_base64"})
