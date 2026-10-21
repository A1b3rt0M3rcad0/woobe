import hashlib
import json
from pathlib import Path


FIXTURE = Path(__file__).parents[2] / "fixtures/artifacts/evaluation/v1"


def test_frozen_retrieval_and_generation_corpus_has_the_planned_shape_and_valid_sources():
    documents = json.loads((FIXTURE / "documents.json").read_text())
    queries = json.loads((FIXTURE / "queries.json").read_text())
    generation = json.loads((FIXTURE / "generation_tasks.json").read_text())
    rubric = json.loads((FIXTURE / "rubric.json").read_text())
    by_source = {item["source"]["source_id"]: item for item in documents}

    assert len(documents) == 36
    assert {key: sum(item["format"] == key for item in documents) for key in
            ("pdf_text", "pdf_scan", "docx", "markdown", "image")} == {
                "pdf_text": 12, "pdf_scan": 6, "docx": 6, "markdown": 6, "image": 6,
            }
    assert len(queries) == 80
    assert {key: sum(item["category"] == key for item in queries) for key in
            ("factual_location", "structural_navigation", "cross_reference", "multi_document",
             "table_or_image", "unanswerable")} == {
                "factual_location": 24, "structural_navigation": 24, "cross_reference": 12,
                "multi_document": 8, "table_or_image": 8, "unanswerable": 4,
            }
    assert len(generation) == 20
    assert {key: sum(item["category"] == key for item in generation) for key in
            ("summary", "exercise_questions", "composite_document")} == {
                "summary": 8, "exercise_questions": 8, "composite_document": 4,
            }
    assert rubric["mode"] == "deterministic_provider_neutral_contract"
    assert "does not score semantic answer quality" in rubric["limitation"]

    for document in documents:
        content = document["synthetic_content"].encode()
        assert hashlib.sha256(content).hexdigest() == document["content_sha256"]
        source = document["source"]
        assert source["source_sha256"] == document["content_sha256"]
        assert source["locator"]["char_end"] == len(content.decode())
    for query in queries:
        assert query["answerable"] is bool(query["gold_source_ids"])
        assert len(query["gold_source_ids"]) == len(query["expected_locators"])
        for source_id, locator in zip(query["gold_source_ids"], query["expected_locators"], strict=True):
            assert source_id in by_source
            assert locator == by_source[source_id]["source"]["locator"]
            assert by_source[source_id]["workspace_id"] in query["workspace_ids"]
    for task in generation:
        assert task["provider_required"] is False
        assert set(task["expected_source_ids"]) <= by_source.keys()
        assert all(set(claim_sources) <= by_source.keys() for claim_sources in task["claim_source_ids"])
