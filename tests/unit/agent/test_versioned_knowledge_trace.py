from modules.agent.infra.execution.trace_event_builder import build_operation_events


def test_rag_timeline_item_becomes_versioned_retrieval_event():
    events = build_operation_events(
        "trace-1",
        [
            {
                "kind": "rag",
                "occurred_at": "2026-07-05T12:00:00+00:00",
                "payload": {
                    "started_at": "2026-07-05T11:59:59+00:00",
                    "ended_at": "2026-07-05T12:00:00+00:00",
                    "knowledge_version_id": "knowledge-1",
                    "vector_snapshot_id": "snapshot-3",
                    "vector_snapshot_version": "v3",
                    "snapshot_hash": "immutable-hash",
                    "embedding_model": "openai/text-embedding-3-small",
                    "rag_runtime_config": {
                        "candidate_k": 20,
                        "top_k": 5,
                        "min_score": 0.7,
                    },
                    "rag_runtime_config_source": "production",
                    "matched_chunks": 3,
                },
            }
        ],
    )

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "rag.retrieval.completed"
    assert event["phase"] == "retrieval"
    assert event["attributes"]["knowledge_version_id"] == "knowledge-1"
    assert event["attributes"]["vector_snapshot_id"] == "snapshot-3"
    assert event["attributes"]["snapshot_hash"] == "immutable-hash"
    assert event["attributes"]["rag_runtime_config"]["top_k"] == 5
    assert event["attributes"]["rag_runtime_config_source"] == "production"
    assert event["attributes"]["matched_chunks"] == 3
