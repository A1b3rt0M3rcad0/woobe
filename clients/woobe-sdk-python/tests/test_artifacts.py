from __future__ import annotations

import asyncio
import hashlib
import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest

from woobe import (
    ArtifactReference,
    ArtifactUploadUncertainError,
    Woobe,
    artifact_part,
    text_part,
)
from woobe._transport.sse import SseFrame
from woobe.errors import (
    WoobeConnectionError,
    WoobeProtocolError,
    WoobeRecoveryError,
    WoobeRequestError,
)
from woobe.events import WoobeEvent
from woobe.results import ChatResult

_CANONICAL_RUNTIME_FIXTURE = (
    Path(__file__).resolve().parents[3] / "specs/runtime/v2/artifact_run.json"
)
_GO_RUNTIME_FIXTURE = (
    Path(__file__).resolve().parents[3] / "clients/woobe-sdk-go/testdata/artifact_run.json"
)
_SDK_RUNTIME_FIXTURE = Path(__file__).parent / "testdata/artifact_run.json"


def _load_runtime_fixture() -> dict:
    embedded = _SDK_RUNTIME_FIXTURE.read_bytes()
    if _CANONICAL_RUNTIME_FIXTURE.exists():
        assert embedded == _CANONICAL_RUNTIME_FIXTURE.read_bytes()
    if _GO_RUNTIME_FIXTURE.exists():
        assert embedded == _GO_RUNTIME_FIXTURE.read_bytes()
    return json.loads(embedded)


@pytest.mark.asyncio
async def test_agent_and_network_content_parts_match_shared_runtime_fixture() -> None:
    fixture = _load_runtime_fixture()
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append({"path": request.url.path, "body": json.loads(request.content)})
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=b"")

    woobe = Woobe(base_url="https://runtime.test", max_reconnect_attempts=0)
    woobe._transport._client = httpx.AsyncClient(
        base_url="https://runtime.test", transport=httpx.MockTransport(handler)
    )
    parts = [
        text_part("Resuma este material e cite a página."),
        artifact_part(
            ArtifactReference(artifact_id="artifact-source-1", revision_id="revision-source-2"),
            "application/pdf",
        ),
    ]
    expected_context = {"course": "course-17", "turn": 9}

    for target in (
        woobe.connect.agent(alias="tutor", key="rk-agent"),
        woobe.connect.network(alias="study-pipeline", key="rk-network"),
    ):
        chat = target.chat_parts(parts, external_context=expected_context)
        assert chat.run_id is None
        with pytest.raises(WoobeRecoveryError):
            _ = [event async for event in chat.events()]

    await woobe.aclose()
    assert [request["path"] for request in captured] == ["/v1/run/stream", "/v1/run/stream"]
    for request, fixture_key in zip(captured, ("agent_request", "network_request"), strict=True):
        expected = fixture[fixture_key]
        assert request["body"] == expected
        assert request["body"]["external_context"] == expected_context


def test_content_part_limits_and_ambiguous_legacy_input_fail_before_http() -> None:
    woobe = Woobe(base_url="http://unused")
    agent = woobe.connect.agent(alias="tutor", key="runtime-key")
    ref = ArtifactReference(artifact_id="artifact-1", revision_id="revision-1")
    with pytest.raises(ValueError):
        agent.chat(input="legacy", content_parts=[text_part("parts")])
    with pytest.raises(ValueError):
        agent.chat_parts([artifact_part(ref) for _ in range(17)])
    with pytest.raises(ValueError):
        agent.chat_parts([text_part("x" * 32_001)])


def test_artifact_result_events_and_image_only_result_are_typed() -> None:
    fixture = _load_runtime_fixture()
    event = WoobeEvent.model_validate(fixture["artifact_available"])
    output = event.artifact_available()
    assert output is not None
    assert output.ref.revision_id == "revision-output-1"
    assert output.run_id == "run-17"

    done = WoobeEvent.model_validate(fixture["completed"])
    result = ChatResult.from_event(done)
    assert result.answer == "O prazo é de um ano. [p. 3]"
    assert result.output_artifacts[0].ref.revision_id == "revision-output-1"
    assert result.source_refs[0].locator is not None
    assert result.source_refs[0].locator.page_number == 3

    image = ChatResult.from_event(WoobeEvent.model_validate(fixture["image_only_completed"]))
    assert image.answer == ""
    assert image.output_artifacts[0].content_type == "image/png"

    malformed = WoobeEvent(
        event_id="event-invalid",
        run_id="run-1",
        session_id="session-1",
        run_kind="AGENT",
        sequence=1,
        type="artifact.available",
        occurred_at="2026-10-20T12:00:00Z",
        payload={
            "artifact_id": "artifact-1",
            "revision_id": "revision-1",
            "path": "x",
            "content_type": "text/plain",
            "size_bytes": 1,
            "sha256": "bad",
            "status": "available",
        },
    )
    with pytest.raises(WoobeProtocolError):
        malformed.artifact_available()


@pytest.mark.asyncio
async def test_artifacts_client_fixes_scope_refuses_redirect_and_streams_upload_parts() -> None:
    captured: list[tuple[str, str, bytes, dict[str, str]]] = []
    part_count = 0

    def upload_response(offset: int = 0, status: str = "uploading") -> dict:
        return {
            "schema_version": "1",
            "id": "upload-1",
            "workspace_id": "workspace-1",
            "operation_id": "operation-1",
            "expected_size": 8,
            "status": status,
            "offset": offset,
        }

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal part_count
        captured.append((request.method, request.url.path, request.content, dict(request.headers)))
        assert request.url.params["project_id"] == "project-1"
        assert request.url.params["environment"] == "staging"
        assert request.headers["Authorization"] == "Bearer runtime-key"
        if request.url.path == "/v1/artifact-capabilities":
            return httpx.Response(
                200,
                json={"max_upload_bytes": 100, "max_upload_part_bytes": 4, "max_upload_parts": 25},
            )
        if request.url.path.endswith("/uploads") and request.method == "POST":
            return httpx.Response(201, json=upload_response())
        if request.url.path.endswith("/parts"):
            part_count += 1
            return httpx.Response(200, json=upload_response(part_count * 4))
        if request.url.path.endswith("/finalize"):
            return httpx.Response(
                200,
                json={
                    **upload_response(8, "completed"),
                    "receipt": {"artifact_id": "artifact-1", "revision_id": "revision-1"},
                },
            )
        return httpx.Response(302, headers={"Location": "https://other.test/steal"})

    woobe = Woobe(base_url="https://runtime.test")
    woobe._transport._client = httpx.AsyncClient(
        base_url="https://runtime.test", transport=httpx.MockTransport(handler)
    )
    artifacts = woobe.artifacts(
        project_id="project-1", runtime_key="runtime-key", environment="staging"
    )
    content = b"abcdefgh"
    uploaded = await artifacts.upload_file(
        "workspace-1",
        BytesIO(content),
        operation_id="operation-1",
        path="folder with spaces/資料.pdf",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        content_type="application/pdf",
    )
    assert uploaded.status == "completed"
    part_requests = [entry for entry in captured if entry[1].endswith("/parts")]
    assert [entry[2] for entry in part_requests] == [b"abcd", b"efgh"]
    assert [entry[0] for entry in part_requests] == ["PUT", "PUT"]
    assert captured[-1][1].endswith("/finalize")

    before_redirect = len(captured)
    with pytest.raises(WoobeRequestError) as caught:
        await artifacts.list_artifacts("workspace-1")
    assert caught.value.status_code == 302
    assert len(captured) == before_redirect + 1
    await woobe.aclose()


@pytest.mark.asyncio
async def test_lost_part_ack_returns_upload_id_without_retry() -> None:
    requests: list[str] = []

    def upload_response() -> dict:
        return {
            "schema_version": "1",
            "id": "upload-uncertain",
            "workspace_id": "workspace-1",
            "operation_id": "operation-1",
            "expected_size": 4,
            "status": "uploading",
            "offset": 0,
        }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path == "/v1/artifact-capabilities":
            return httpx.Response(
                200,
                json={"max_upload_bytes": 100, "max_upload_part_bytes": 4, "max_upload_parts": 25},
            )
        if request.method == "POST" and request.url.path.endswith("/uploads"):
            return httpx.Response(201, json=upload_response())
        if request.url.path.endswith("/parts"):
            raise httpx.ConnectError("ACK lost", request=request)
        return httpx.Response(200, json=upload_response())

    woobe = Woobe(base_url="https://runtime.test")
    woobe._transport._client = httpx.AsyncClient(
        base_url="https://runtime.test", transport=httpx.MockTransport(handler)
    )
    artifacts = woobe.artifacts(project_id="project-1", runtime_key="runtime-key")
    with pytest.raises(ArtifactUploadUncertainError) as caught:
        await artifacts.upload_file(
            "workspace-1",
            BytesIO(b"data"),
            operation_id="operation-1",
            path="x.txt",
            size_bytes=4,
            sha256=hashlib.sha256(b"data").hexdigest(),
            content_type="text/plain",
        )
    assert caught.value.upload_id == "upload-uncertain"
    assert sum(path.endswith("/parts") for path in requests) == 1
    assert not any(path.endswith("/finalize") for path in requests)
    await woobe.aclose()


@pytest.mark.asyncio
async def test_hash_mismatch_aborts_staging_and_cancellation_cleans_up() -> None:
    requests: list[tuple[str, str]] = []
    cancel_part = False

    def upload_response(status: str = "uploading") -> dict:
        return {
            "schema_version": "1",
            "id": "upload-cleanup",
            "workspace_id": "workspace-1",
            "operation_id": "operation-1",
            "expected_size": 4,
            "status": status,
            "offset": 0,
        }

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal cancel_part
        requests.append((request.method, request.url.path))
        if request.url.path == "/v1/artifact-capabilities":
            return httpx.Response(
                200,
                json={
                    "max_upload_bytes": 100,
                    "max_upload_part_bytes": 4,
                    "max_upload_parts": 25,
                },
            )
        if request.method == "POST" and request.url.path.endswith("/uploads"):
            return httpx.Response(201, json=upload_response())
        if request.url.path.endswith("/parts"):
            if cancel_part:
                raise asyncio.CancelledError()
            return httpx.Response(200, json=upload_response())
        if request.method == "DELETE" and request.url.path.endswith("/uploads/upload-cleanup"):
            return httpx.Response(200, json=upload_response("aborted"))
        return httpx.Response(500)

    woobe = Woobe(base_url="https://runtime.test")
    woobe._transport._client = httpx.AsyncClient(
        base_url="https://runtime.test", transport=httpx.MockTransport(handler)
    )
    artifacts = woobe.artifacts(project_id="project-1", runtime_key="runtime-key")
    with pytest.raises(ValueError, match="SHA-256"):
        await artifacts.upload_file(
            "workspace-1",
            BytesIO(b"data"),
            operation_id="operation-1",
            path="x.txt",
            size_bytes=4,
            sha256="b" * 64,
            content_type="text/plain",
        )
    assert ("DELETE", "/v1/artifact-workspaces/workspace-1/uploads/upload-cleanup") in requests

    cancel_part = True
    requests.clear()
    with pytest.raises(asyncio.CancelledError):
        await artifacts.upload_file(
            "workspace-1",
            BytesIO(b"data"),
            operation_id="operation-1",
            path="x.txt",
            size_bytes=4,
            sha256=hashlib.sha256(b"data").hexdigest(),
            content_type="text/plain",
        )
    assert ("DELETE", "/v1/artifact-workspaces/workspace-1/uploads/upload-cleanup") in requests
    await woobe.aclose()


@pytest.mark.asyncio
async def test_download_is_exact_revision_stream_and_closes_response() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["range"] = request.headers.get("Range")
        captured["query"] = dict(request.url.params)
        return httpx.Response(
            206,
            headers={
                "Content-Type": "application/pdf",
                "Content-Range": "bytes 2-4/6",
                "ETag": '"digest"',
                "X-Woobe-Source-Sha256": "a" * 64,
            },
            content=b"cde",
        )

    woobe = Woobe(base_url="https://runtime.test")
    woobe._transport._client = httpx.AsyncClient(
        base_url="https://runtime.test", transport=httpx.MockTransport(handler)
    )
    artifacts = woobe.artifacts(
        project_id="project-1", runtime_key="runtime-key", environment="draft"
    )
    async with await artifacts.download(
        "workspace-1",
        ArtifactReference(artifact_id="artifact-1", revision_id="revision-2"),
        range_header="bytes=2-4",
    ) as download:
        chunks = [chunk async for chunk in download.iter_bytes(2)]
        assert b"".join(chunks) == b"cde"
        assert download.status_code == 206
        assert download.sha256 == "a" * 64
    assert captured["path"].endswith("/artifacts/artifact-1/revisions/revision-2/content")
    assert captured["range"] == "bytes=2-4"
    assert captured["query"] == {
        "artifact_workspace_id": "workspace-1",
        "project_id": "project-1",
        "environment": "draft",
    }
    await woobe.aclose()


@pytest.mark.asyncio
async def test_synchronous_network_run_uses_shared_fixture_and_typed_receipts() -> None:
    fixture = _load_runtime_fixture()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        payload = fixture["completed"]["payload"]
        return httpx.Response(
            200,
            json={
                "success": True,
                "message": "ok",
                "data": {
                    "answer": payload["answer"],
                    "output_artifacts": payload["output_artifacts"],
                    "source_refs": payload["source_refs"],
                },
            },
        )

    woobe = Woobe(base_url="https://runtime.test")
    woobe._transport._client = httpx.AsyncClient(
        base_url="https://runtime.test", transport=httpx.MockTransport(handler)
    )
    target = woobe.connect.network(alias="pipeline", key="runtime-key")
    parts = [
        text_part("Resuma este material e cite a página."),
        artifact_part(
            ArtifactReference(artifact_id="artifact-source-1", revision_id="revision-source-2"),
            "application/pdf",
        ),
    ]
    result = await target.run(
        content_parts=parts,
        external_context={"course": "course-17", "turn": 9},
    )
    await woobe.aclose()
    assert captured == {"path": "/v1/run", "body": fixture["network_request"]}
    assert result.success is True
    assert result.data["answer"] == "O prazo é de um ano. [p. 3]"
    assert result.output_artifacts[1].content_type == "image/png"
    assert result.source_refs[0].revision_id == "revision-source-2"


@pytest.mark.asyncio
async def test_reattach_run_state_replaces_lost_artifact_sequence_without_new_post() -> None:
    fixture = _load_runtime_fixture()

    class ReattachTransport:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.external_contexts: list[dict | None] = []

        async def aclose(self) -> None:
            return None

        async def stream_new_run(self, **kwargs):
            self.calls.append("post")
            self.external_contexts.append(kwargs["external_context"])
            yield SseFrame(event="artifact.available", data=fixture["artifact_available"])
            raise WoobeConnectionError("stream disconnected")

        async def stream_run(self, *, key: str, run_id: str):
            assert key == "runtime-key"
            assert run_id == "run-17"
            self.calls.append("reattach")
            state = dict(fixture["completed"])
            state["type"] = "run.state"
            state["sequence"] = 5
            state["payload"] = {**state["payload"], "status": "completed"}
            yield SseFrame(event="run.state", data=state)

        async def resolve_active_run(self, **kwargs):
            del kwargs
            return None

    transport = ReattachTransport()
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport  # type: ignore[assignment]
    chat = woobe.connect.agent(alias="tutor", key="runtime-key").chat(
        input="Olá", external_context={"course": "course-17"}
    )
    events = [event async for event in chat.events()]
    assert [event.type for event in events] == ["artifact.available", "run.state"]
    assert transport.calls == ["post", "reattach"]
    assert transport.external_contexts == [{"course": "course-17"}]
    assert chat.result is not None
    assert len(chat.result.output_artifacts) == 2
    await woobe.aclose()
