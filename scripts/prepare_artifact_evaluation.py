"""Build the fixed, provider-neutral Artifact retrieval evaluation corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests/fixtures/artifacts/evaluation/v1"
FORMATS = (
    [("pdf_text", 12), ("pdf_scan", 6), ("docx", 6), ("markdown", 6), ("image", 6)]
)


def _document(index: int, format_name: str) -> dict:
    document_id = f"doc-{index:03d}"
    workspace_id = f"eval-workspace-{(index - 1) // 6 + 1:02d}"
    artifact_id = f"eval-artifact-{index:03d}"
    revision_id = f"eval-revision-{index:03d}"
    block_id = f"eval-block-{index:03d}"
    content = (
        f"Synthetic evaluation document {index:03d}.\n"
        f"Fact: evaluation marker {index:03d} is cobalt-{index:03d}.\n"
        f"Section: chapter-{index:03d}/appendix-{index:03d}.\n"
        f"Table: row-{index:03d} value is {index * 7}.\n"
        f"Figure: diagram-{index:03d} labels the same evaluation marker.\n"
    )
    return {
        "document_id": document_id,
        "format": format_name,
        "workspace_id": workspace_id,
        "artifact_id": artifact_id,
        "revision_id": revision_id,
        "path": f"corpus/{document_id}.{ {'pdf_text':'pdf','pdf_scan':'pdf','docx':'docx','markdown':'md','image':'png'}[format_name] }",
        "synthetic_content": content,
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "source": {
            "source_id": f"source-{index:03d}",
            "workspace_id": workspace_id,
            "artifact_id": artifact_id,
            "revision_id": revision_id,
            "source_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "representation_set_id": f"eval-representation-{index:03d}",
            "index_id": f"eval-index-{index:03d}",
            "locator": {
                "block_id": block_id,
                "char_start": 0,
                "char_end": len(content),
                "char_space": "canonical_block_text",
            },
        },
    }


def build() -> dict[str, list[dict]]:
    formats = [name for name, count in FORMATS for _ in range(count)]
    documents = [_document(index, formats[index - 1]) for index in range(1, 37)]

    def query(query_id, category, text, document_indexes, *, answerable=True, method="text"):
        return {
            "query_id": query_id,
            "category": category,
            "query": text,
            "answerable": answerable,
            "retrieval_method": method,
            "workspace_ids": sorted({documents[i - 1]["workspace_id"] for i in document_indexes}),
            "gold_source_ids": [documents[i - 1]["source"]["source_id"] for i in document_indexes],
            "expected_locators": [documents[i - 1]["source"]["locator"] for i in document_indexes],
            "result_budget": 10,
        }

    queries = []
    for index in range(1, 25):
        queries.append(query(f"fact-{index:02d}", "factual_location",
            f"Which document contains cobalt-{index:03d}?", [index]))
    for index in range(1, 25):
        queries.append(query(f"tree-{index:02d}", "structural_navigation",
            f"Open chapter-{index:03d} and appendix-{index:03d}.", [index], method="tree"))
    for index in range(1, 13):
        appendix = index + 24
        queries.append(query(f"xref-{index:02d}", "cross_reference",
            f"Follow appendix-{index:03d} to its document reference.", [index, appendix]))
    for index in range(1, 9):
        other = index + 8
        queries.append(query(f"multi-{index:02d}", "multi_document",
            f"Compare cobalt-{index:03d} with cobalt-{other:03d}.", [index, other]))
    for index in range(25, 31):
        queries.append(query(f"table-{index - 24:02d}", "table_or_image",
            f"What value appears in row-{index:03d}?", [index]))
    for index in range(31, 33):
        queries.append(query(f"image-{index - 30:02d}", "table_or_image",
            f"Which marker is labeled by diagram-{index:03d}?", [index]))
    for index in range(1, 5):
        queries.append(query(f"unanswerable-{index:02d}", "unanswerable",
            f"What is the unsupported secret-{index:03d}?", [], answerable=False))

    generation = []
    for index in range(1, 9):
        ids = [index, index + 1]
        generation.append({
            "task_id": f"summary-{index:02d}", "category": "summary",
            "prompt": f"Summarize synthetic markers {index:03d} and {index + 1:03d}.",
            "expected_source_ids": [documents[i - 1]["source"]["source_id"] for i in ids],
            "claim_source_ids": [[documents[i - 1]["source"]["source_id"]] for i in ids],
            "required_format": "numbered_summary", "provider_required": False,
        })
    for index in range(9, 17):
        ids = [index]
        generation.append({
            "task_id": f"exercise-{index - 8:02d}", "category": "exercise_questions",
            "prompt": f"Write two questions about chapter-{index:03d} with answer keys.",
            "expected_source_ids": [documents[i - 1]["source"]["source_id"] for i in ids],
            "claim_source_ids": [[documents[ids[0] - 1]["source"]["source_id"]] for _ in range(2)],
            "required_format": "questions_with_answer_key", "provider_required": False,
        })
    for index in range(17, 21):
        ids = [index, index + 1, index + 2]
        generation.append({
            "task_id": f"composite-{index - 16:02d}", "category": "composite_document",
            "prompt": f"Compose a short report with a table and references for marker {index:03d}.",
            "expected_source_ids": [documents[i - 1]["source"]["source_id"] for i in ids],
            "claim_source_ids": [[documents[i - 1]["source"]["source_id"]] for i in ids],
            "required_format": "markdown_with_citations", "provider_required": False,
        })
    return {"documents": documents, "queries": queries, "generation_tasks": generation}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, value in build().items():
        (OUTPUT / f"{name}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    (OUTPUT / "rubric.json").write_text(json.dumps({
        "schema_version": 1,
        "mode": "deterministic_provider_neutral_contract",
        "metrics": ["gold_source_recall", "locator_validity", "authorized_workspace_scope", "abstention_on_unanswerable"],
        "acceptance": {
            "unauthorized_sources_accepted": 0,
            "invalid_locators_accepted": 0,
            "cross_workspace_leaks": 0,
            "unanswerable_queries_with_cited_answer": 0,
        },
        "limitation": "This fixture validates retrieval/source contracts; it does not score semantic answer quality or qualify a live provider.",
    }, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
