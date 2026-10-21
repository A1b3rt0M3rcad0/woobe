from uuid import uuid4

from shared.contracts.run_event_journal import DurableRunEvent
from shared.runtime.journal_projection import _public_runtime_event


def _event(event_type: str, payload: dict) -> DurableRunEvent:
    return DurableRunEvent(
        run_id=uuid4(),
        run_kind="agent",
        sequence=1,
        event_id="event-1",
        event_type=event_type,
        occurred_at="2026-10-21T00:00:00+00:00",
        schema_version=1,
        storage_version="v2",
        metadata={},
        payload=payload,
    )


def test_artifact_available_public_projection_contains_metadata_only() -> None:
    event_type, payload = _public_runtime_event(
        _event(
            "artifact.available",
            {
                "artifact_id": "artifact-1",
                "revision_id": "revision-2",
                "path": "outputs/result.txt",
                "content_type": "text/plain",
                "size_bytes": 4,
                "sha256": "a" * 64,
                "status": "available",
                "run_id": "run-1",
                "node_id": None,
                "blob": "private file bytes",
                "authorization": "private credential",
            },
        )
    )

    assert event_type == "artifact_available"
    assert payload == {
        "artifact_id": "artifact-1",
        "revision_id": "revision-2",
        "path": "outputs/result.txt",
        "content_type": "text/plain",
        "size_bytes": 4,
        "sha256": "a" * 64,
        "status": "available",
        "run_id": "run-1",
    }


def test_terminal_projection_allows_refs_but_strips_private_tool_payloads() -> None:
    artifact = {
        "schema_version": "1",
        "ref": {"artifact_id": "artifact-1", "revision_id": "revision-2"},
        "path": "outputs/result.txt",
        "content_type": "text/plain",
        "size_bytes": 4,
        "sha256": "a" * 64,
        "status": "available",
        "source_refs": [],
    }
    source = {
        "artifact_id": "source-1",
        "revision_id": "revision-8",
        "source_sha256": "b" * 64,
    }
    event_type, payload = _public_runtime_event(
        _event(
            "run.completed",
            {
                "answer": "Done",
                "output_artifacts": [artifact],
                "source_refs": [source],
                "tool_calls": [{"output": "private excerpt"}],
                "prompt": "private prompt",
                "api_key": "private credential",
            },
        )
    )

    assert event_type == "execution_completed"
    assert payload["result"]["output_artifacts"] == [artifact]
    assert payload["result"]["source_refs"] == [source]
    assert "tool_calls" not in payload
    assert "prompt" not in payload
    assert "api_key" not in payload


def test_transfer_journal_projection_contains_only_reconciliation_metadata() -> None:
    event_type, payload = _public_runtime_event(
        _event(
            "artifact.transfer.uncertain",
            {
                "operation_id": "operation-1",
                "state": "uncertain",
                "mode": "multipart",
                "destination_host": "processor.example",
                "input_refs": [{"artifact_id": "artifact-1", "revision_id": "revision-2"}],
                "file_hashes": [{"sha256": "a" * 64, "size_bytes": 16}],
                "status_code": None,
                "tool_id": "tool-1",
                "url": "https://processor.example/upload?token=private",
                "blob": "private file bytes",
                "authorization": "Bearer private",
            },
        )
    )

    assert event_type == "artifact_transfer"
    assert payload["operation_id"] == "operation-1"
    assert payload["state"] == "uncertain"
    assert payload["destination_host"] == "processor.example"
    assert "url" not in payload
    assert "blob" not in payload
    assert "authorization" not in payload
