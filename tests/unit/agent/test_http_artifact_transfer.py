from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.http_tool_contract import compile_http_tool_contract
from modules.agent.infra.adapters.http_artifact_transfer import (
    prepare_http_artifact_transfer,
    scrub_temporary_urls,
)
from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
from modules.agent.application.interfaces.ports import ExecutionResult
from modules.agent.infra.adapters import tool_executor as http_executor_module
from modules.agent.infra.adapters.tool_runtime import HttpToolRuntime
from shared.contracts.artifact_transfer import ArtifactTransferSource


def _contract(mode: str = "multipart"):
    config = {
        "protocol": "http",
        "url": "https://processor.example/v1/ingest",
        "method": "POST",
        "file_bindings": [{
            "input_name": "document",
            "mode": mode,
            "part_name": "input_file",
            "content_types": ["application/pdf"],
            "max_bytes": 1024,
            "idempotency_header": "Idempotency-Key",
        }],
    }
    if mode == "url":
        config["body"] = {"document_url": "{{document}}"}
        config["headers"] = [{"key": "Content-Type", "value": "application/json"}]
    return compile_http_tool_contract(config)


def _source(content: bytes) -> ArtifactTransferSource:
    async def chunks() -> AsyncIterator[bytes]:
        yield content[:3]
        yield content[3:]

    import hashlib

    return ArtifactTransferSource(
        artifact_id="artifact-1",
        revision_id="revision-4",
        path="incoming/report.pdf",
        content_type="application/pdf",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        content=chunks(),
    )


async def _collect(stream: AsyncIterator[bytes]) -> bytes:
    data = bytearray()
    async for chunk in stream:
        data.extend(chunk)
    return bytes(data)


@pytest.mark.asyncio
async def test_multipart_transfer_streams_exact_revision_and_emits_safe_receipt():
    content = b"%PDF-1.7 sample"

    async def resolve(artifact_id: str, revision_id: str):
        assert (artifact_id, revision_id) == ("artifact-1", "revision-4")
        return _source(content)

    contract = _contract()
    prepared = await prepare_http_artifact_transfer(
        contract,
        {"document": {"artifact_id": "artifact-1", "revision_id": "revision-4"}},
        url=contract.config["url"],
        headers={},
        body=None,
        transfer_resolver=resolve,
        run_id=str(uuid4()),
        tool_id="tool-1",
    )

    assert prepared is not None
    payload = await _collect(prepared.body)
    assert b'name="input_file"; filename="report.pdf"' in payload
    assert b"Content-Type: application/pdf" in payload
    assert content in payload
    assert int(prepared.headers["Content-Length"]) == len(payload)
    assert prepared.headers["Idempotency-Key"] == prepared.operation_id
    receipt = prepared.receipt("completed")
    assert receipt["input_refs"] == [{"artifact_id": "artifact-1", "revision_id": "revision-4"}]
    assert receipt["file_hashes"][0]["sha256"] == _source(content).sha256
    assert content.decode("ascii") not in str(receipt)


@pytest.mark.asyncio
async def test_raw_bytes_transfer_is_streamed_with_verified_length():
    content = b"%PDF-1.7"
    contract = _contract("bytes")

    async def resolve(_artifact_id: str, _revision_id: str):
        return _source(content)

    prepared = await prepare_http_artifact_transfer(
        contract,
        {"document": {"artifact_id": "artifact-1", "revision_id": "revision-4"}},
        url=contract.config["url"],
        headers={},
        body=None,
        transfer_resolver=resolve,
        run_id="run-1",
        tool_id="tool-1",
    )
    assert prepared is not None
    assert prepared.mode == "bytes"
    assert prepared.headers["Content-Type"] == "application/pdf"
    assert int(prepared.headers["Content-Length"]) == len(content)
    assert await _collect(prepared.body) == content


@pytest.mark.asyncio
async def test_transfer_rejects_unbound_references_and_incompatible_media():
    contract = _contract()

    async def resolve(_artifact_id: str, _revision_id: str):
        return _source(b"data")

    with pytest.raises(PermissionError, match="not authorized"):
        await prepare_http_artifact_transfer(
            contract,
            {"document": {"artifact_id": "artifact-1", "revision_id": "revision-4"}},
            url=contract.config["url"],
            headers={}, body=None, transfer_resolver=None,
            run_id="run-1", tool_id="tool-1",
        )

    contract.config["file_bindings"][0]["content_types"] = ["image/png"]
    with pytest.raises(ValueError, match="media type"):
        await prepare_http_artifact_transfer(
            contract,
            {"document": {"artifact_id": "artifact-1", "revision_id": "revision-4"}},
            url=contract.config["url"],
            headers={}, body=None, transfer_resolver=resolve,
            run_id="run-1", tool_id="tool-1",
        )


@pytest.mark.asyncio
async def test_temporary_url_is_short_lived_and_not_in_receipt(monkeypatch):
    contract = _contract("url")
    temporary_url = "https://bucket.example/object?X-Amz-Signature=short-secret"
    source = ArtifactTransferSource(
        artifact_id="artifact-1",
        revision_id="revision-4",
        path="incoming/report.pdf",
        content_type="application/pdf",
        size_bytes=10,
        sha256="a" * 64,
        temporary_url=temporary_url,
        expires_in_seconds=60,
    )
    recipients = []

    async def resolve(artifact_id, revision_id, recipient_host):
        recipients.append((artifact_id, revision_id, recipient_host))
        return source

    monkeypatch.setattr(
        http_executor_module,
        "_validated_public_addresses",
        lambda _url: frozenset({"203.0.113.8"}),
    )
    prepared = await prepare_http_artifact_transfer(
        contract,
        {"document": {"artifact_id": "artifact-1", "revision_id": "revision-4"}},
        url=contract.config["url"],
        headers={"Content-Type": "application/json"},
        body='{"document_url":"https://temporary-url.invalid/"}',
        transfer_resolver=None,
        url_resolver=resolve,
        run_id="run-1",
        tool_id="tool-1",
    )

    assert prepared is not None
    assert recipients == [("artifact-1", "revision-4", "processor.example")]
    assert prepared.render_inputs == {"document": temporary_url}
    assert "short-secret" not in str(prepared.receipt("completed"))
    assert scrub_temporary_urls(temporary_url, prepared) == "[REDACTED TEMPORARY ARTIFACT URL]"


@pytest.mark.asyncio
async def test_http_tool_records_durable_transfer_receipt_without_file_bytes():
    content = b"%PDF-1.7"
    seen = {}
    events = []

    class Executor:
        async def execute(self, *, method, url, headers, body, timeout_ms):
            seen["method"] = method
            seen["url"] = url
            seen["headers"] = dict(headers)
            seen["body"] = await _collect(body)
            return ExecutionResult(success=True, status_code=200, output={"status_code": 200})

    class Recorder:
        async def emit(self, event_type, payload, *, durable):
            assert durable is True
            events.append((event_type, payload))

    async def resolve(_artifact_id: str, _revision_id: str):
        return _source(content)

    context = new_execution_context()
    context.run_id = uuid4()
    context.project_id = uuid4()
    context.artifact_transfer_resolver = resolve
    context.run_event_recorder = Recorder()
    token = current_execution.set(context)
    try:
        runtime = HttpToolRuntime(Executor())
        tool = type("HttpTool", (), {
            "id": "tool-1",
            "project_id": context.project_id,
            "config": {
                **_contract().config,
                "permission": {"mode": "allow"},
            },
            "input_schema": _contract().input_schema,
            "timeout_ms": 5000,
        })()
        result = await runtime.execute(
            tool,
            {"document": {"artifact_id": "artifact-1", "revision_id": "revision-4"}},
        )
    finally:
        current_execution.reset(token)

    assert result.success is True
    assert seen["method"] == "POST"
    assert seen["url"] == "https://processor.example/v1/ingest"
    assert content in seen["body"]
    assert result.output["artifact_transfer"]["state"] == "completed"
    assert [event for event, _payload in events] == [
        "artifact.transfer.started", "artifact.transfer.completed",
    ]
    assert content.decode("ascii") not in str(events)


@pytest.mark.asyncio
async def test_http_tool_scrubs_temporary_url_from_external_response(monkeypatch):
    temporary_url = "https://bucket.example/object?X-Amz-Signature=private"
    source = ArtifactTransferSource(
        artifact_id="artifact-1",
        revision_id="revision-4",
        path="incoming/report.pdf",
        content_type="application/pdf",
        size_bytes=10,
        sha256="a" * 64,
        temporary_url=temporary_url,
        expires_in_seconds=60,
    )
    sent = {}

    async def resolve(_artifact_id, _revision_id, recipient_host):
        assert recipient_host == "processor.example"
        return source

    class Executor:
        async def execute(self, *, method, url, headers, body, timeout_ms):
            sent["body"] = body
            return ExecutionResult(success=True, status_code=200, output={"echo": temporary_url})

    monkeypatch.setattr(
        http_executor_module,
        "_validated_public_addresses",
        lambda _url: frozenset({"203.0.113.8"}),
    )
    context = new_execution_context()
    context.run_id = uuid4()
    context.project_id = uuid4()
    context.artifact_transfer_url_resolver = resolve
    token = current_execution.set(context)
    try:
        runtime = HttpToolRuntime(Executor())
        contract = _contract("url")
        tool = type("HttpTool", (), {
            "id": "tool-1",
            "project_id": context.project_id,
            "config": {**contract.config, "permission": {"mode": "allow"}},
            "input_schema": contract.input_schema,
            "timeout_ms": 5000,
        })()
        result = await runtime.execute(
            tool,
            {"document": {"artifact_id": "artifact-1", "revision_id": "revision-4"}},
        )
    finally:
        current_execution.reset(token)

    assert temporary_url in sent["body"]
    assert temporary_url not in str(result.output)
    assert result.output["echo"] == "[REDACTED TEMPORARY ARTIFACT URL]"


@pytest.mark.asyncio
async def test_http_executor_sends_async_artifact_body_without_following_redirects(monkeypatch):
    import httpx

    monkeypatch.setattr(
        http_executor_module,
        "_validated_public_addresses",
        lambda _url: frozenset({"203.0.113.8"}),
    )
    requests = []

    async def handle(request):
        requests.append(request)
        await request.aread()
        return httpx.Response(307, headers={"location": "https://other.example/"})

    async def body():
        yield b"first-"
        yield b"second"

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle), follow_redirects=False)
    executor = http_executor_module.HttpToolExecutor(client=client)
    try:
        result = await executor.execute(
            method="POST",
            url="https://processor.example/ingest",
            headers={"Content-Length": "12"},
            body=body(),
        )
    finally:
        await client.aclose()

    assert result.success is False
    assert result.error == "HTTP redirects are not allowed for tools"
    assert len(requests) == 1
    assert requests[0].content == b"first-second"
