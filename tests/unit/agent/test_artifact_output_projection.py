from types import SimpleNamespace

from modules.agent.application.interfaces.artifact_output_projection import project_artifact_outputs


def _tool(name: str, output: dict, *, success: bool = True):
    return SimpleNamespace(
        tool_name=name,
        output={"success": success, "output": output},
    )


def test_projection_keeps_exact_sources_and_deduplicates_run_outputs() -> None:
    source = {
        "artifact_id": "artifact-1",
        "revision_id": "revision-3",
        "source_sha256": "a" * 64,
        "locator": {"page_number": 2},
    }
    output = {
        "artifact_id": "artifact-2",
        "revision_id": "revision-1",
        "path": "answers/summary.txt",
        "content_type": "text/plain; charset=utf-8",
        "size_bytes": 7,
        "sha256": "b" * 64,
    }
    outputs, sources = project_artifact_outputs(
        [
            _tool("woobe_artifact_write", output),
            _tool("woobe_artifact_read", {"source": source, "text": "private excerpt"}),
            _tool("woobe_artifact_write", output),
        ],
        run_id="run-5",
        node_id="node-2",
    )

    assert len(outputs) == 1
    assert outputs[0].ref.artifact_id == "artifact-2"
    assert outputs[0].ref.revision_id == "revision-1"
    assert outputs[0].run_id == "run-5"
    assert outputs[0].node_id == "node-2"
    assert outputs[0].source_refs == (source,)
    assert sources == [source]
    assert "private excerpt" not in str(outputs[0].model_dump(mode="json"))


def test_projection_ignores_failed_or_incomplete_artifact_calls() -> None:
    outputs, sources = project_artifact_outputs(
        [
            _tool(
                "woobe_artifact_write",
                {
                    "artifact_id": "artifact-2",
                    "revision_id": "revision-1",
                    "path": "bad.txt",
                },
            ),
            _tool(
                "woobe_artifact_read",
                {"source": {"artifact_id": "artifact-1", "revision_id": "revision-3"}},
                success=False,
            ),
        ],
        run_id="run-5",
    )
    assert outputs == []
    assert sources == []
