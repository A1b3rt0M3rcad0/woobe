"""Trust metadata for Tool output entering or re-entering model context."""

from typing import Any


def tool_result_context_metadata(
    *, tool_name: str, tool_call_id: str, raw_units: int | None = None,
    compacted: bool = False, parent_ref: str | None = None,
    selection_method: str = "tool_result_materialization",
) -> dict[str, Any]:
    """Preserve source trust when a Tool result enters or re-enters context."""
    artifact_result = tool_name.startswith("woobe_artifact_")
    value: dict[str, Any] = {
        "source_type": "ARTIFACT" if artifact_result else "TOOL",
        "source_ref": str(tool_call_id),
        "selection_method": selection_method,
        "trust": "untrusted_document" if artifact_result else "authenticated_external",
        "sensitivity": "internal",
        "tool_name": tool_name,
    }
    if parent_ref is not None:
        value["parent_ref"] = str(parent_ref)
    if raw_units is not None:
        value["raw_units"] = raw_units
    if compacted:
        value["transformations"] = ["tool_output_compaction"]
    return {"woobe_context": value}
