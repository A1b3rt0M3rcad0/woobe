"""Project exact references from successful Artifact Tool results."""

from __future__ import annotations

import json
from typing import Any

from shared.contracts.artifact_output import ArtifactOutput
from shared.contracts.artifact_reference import ArtifactReference


def _call_value(call: Any, name: str, default=None):
    if isinstance(call, dict):
        return call.get(name, default)
    return getattr(call, name, default)


def _result_output(call: Any) -> dict[str, Any] | None:
    value = _call_value(call, "output")
    if not isinstance(value, dict) or value.get("success") is not True:
        return None
    result = value.get("output")
    return result if isinstance(result, dict) else None


def _source_references(call: Any) -> list[dict[str, Any]]:
    output = _result_output(call)
    if output is None:
        return []
    candidates: list[Any] = []
    if isinstance(output.get("source"), dict):
        candidates.append(output["source"])
    for item in output.get("source_refs", []):
        if isinstance(item, dict):
            candidates.append(item)
    for item in output.get("items", []):
        if isinstance(item, dict) and isinstance(item.get("source"), dict):
            candidates.append(item["source"])
    references: list[dict[str, Any]] = []
    for item in candidates:
        try:
            reference = ArtifactReference.model_validate({
                "artifact_id": item.get("artifact_id"),
                "revision_id": item.get("revision_id"),
            })
        except (TypeError, ValueError):
            continue
        projected = dict(item)
        projected.update(reference.model_dump(mode="json"))
        references.append(projected)
    return references


def project_artifact_outputs(
    tool_calls: list[Any] | tuple[Any, ...], *, run_id: str | None,
    node_id: str | None = None,
) -> tuple[list[ArtifactOutput], list[dict[str, Any]]]:
    """Return deduplicated outputs and exact sources actually returned to the Run."""
    sources: dict[str, dict[str, Any]] = {}
    output_metadata: dict[tuple[str, str], dict[str, Any]] = {}
    for call in tool_calls:
        name = _call_value(call, "tool_name", "")
        result_output = _result_output(call)
        for source in _source_references(call):
            key = json.dumps(source, sort_keys=True, separators=(",", ":"), default=str)
            sources.setdefault(key, source)
        if result_output is not None:
            for raw_artifact in result_output.get("output_artifacts", []):
                if not isinstance(raw_artifact, dict):
                    continue
                try:
                    artifact = ArtifactOutput.model_validate({
                        "ref": raw_artifact.get("ref") or {
                            "artifact_id": raw_artifact.get("artifact_id"),
                            "revision_id": raw_artifact.get("revision_id"),
                        },
                        "path": raw_artifact["path"],
                        "content_type": raw_artifact["content_type"],
                        "size_bytes": raw_artifact["size_bytes"],
                        "sha256": raw_artifact["sha256"],
                        "source_refs": tuple(raw_artifact.get("source_refs") or ()),
                        "run_id": raw_artifact.get("run_id") or run_id,
                        "node_id": raw_artifact.get("node_id") or node_id,
                    })
                except (TypeError, ValueError):
                    continue
                refs = list(artifact.source_refs)
                for source in refs:
                    try:
                        ref = ArtifactReference.model_validate(source)
                    except (TypeError, ValueError):
                        continue
                    item = dict(source)
                    item.update(ref.model_dump(mode="json"))
                    key = json.dumps(item, sort_keys=True, separators=(",", ":"), default=str)
                    sources.setdefault(key, item)
                key = (artifact.ref.artifact_id, artifact.ref.revision_id)
                output_metadata.setdefault(key, artifact.model_dump(mode="python"))
        if name != "woobe_artifact_write":
            continue
        output = result_output
        if output is None:
            continue
        try:
            artifact = ArtifactOutput.model_validate({
                "ref": {
                    "artifact_id": output["artifact_id"],
                    "revision_id": output["revision_id"],
                },
                "path": output["path"],
                "content_type": output["content_type"],
                "size_bytes": output["size_bytes"],
                "sha256": output["sha256"],
                "run_id": run_id,
                "node_id": node_id,
            })
        except (KeyError, TypeError, ValueError):
            continue
        key = (artifact.ref.artifact_id, artifact.ref.revision_id)
        output_metadata.setdefault(key, artifact.model_dump(mode="python"))
    source_refs = list(sources.values())
    output_artifacts = [
        ArtifactOutput.model_validate({**metadata, "source_refs": source_refs})
        for metadata in output_metadata.values()
    ]
    return output_artifacts, source_refs
