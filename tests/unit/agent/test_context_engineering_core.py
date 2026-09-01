from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from modules.agent.application.context_assembly import (
    ContextBudgetExceeded,
    assemble_context,
    enrich_snapshot_with_reported_usage,
)
from modules.agent.application.context_policy import (
    ContextPolicyV1,
    canonicalize_context_runtime_config,
    context_policy_hash,
)
from modules.agent.domain.context import (
    ContextMeasurementStatus,
    ContextPressureStatus,
    ContextPriority,
    ContextSourceType,
)
from shared.contracts.llm_cost import provider_model_pricing_snapshot


def _runtime_context(**overrides):
    defaults = {
        "model_capacity_units": None,
        "reserved_output_units": None,
        "active_tool_definitions": [],
        "context_selection_metadata": {},
        "rag_metadata": {},
        "context_rag_sources": [],
        "parent_invocation_id": None,
        "network_execution_id": None,
        "network_invocation_id": None,
        "network_node_id": None,
        "input_message_id": None,
        "run_id": uuid4(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _assemble(messages, *, policy=None, runtime_context=None):
    return assemble_context(
        messages=messages,
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="openai",
        model="test-model",
        runtime_context=runtime_context or _runtime_context(),
        policy=policy or ContextPolicyV1(),
    )


def test_context_runtime_config_is_canonical_and_preserves_other_runtime_keys():
    runtime = canonicalize_context_runtime_config(
        {
            "timeout_seconds": 30,
            "context": {"session": {"max_messages": 7}},
        }
    )

    assert runtime["timeout_seconds"] == 30
    assert runtime["context"]["schema_version"] == 1
    assert runtime["context"]["session"]["max_messages"] == 7
    assert runtime["context"]["retention"]["materialized_content"] == "references_only"
    assert runtime["context"]["ordering"]["strategy"] == "preserve_input"
    assert runtime["context"]["deduplication"]["strategy"] == "none"
    assert runtime["context"]["source_priorities"]["SYSTEM"] == "MANDATORY"

    policy = ContextPolicyV1.model_validate(runtime["context"])
    assert context_policy_hash(policy) == context_policy_hash(runtime["context"])


def test_context_v1_rejects_retention_modes_not_implemented_by_runtime():
    with pytest.raises(ValidationError, match="references_only"):
        ContextPolicyV1.model_validate(
            {"retention": {"materialized_content": "full"}}
        )


def test_context_pressure_thresholds_must_be_strictly_increasing():
    with pytest.raises(ValidationError):
        ContextPolicyV1.model_validate(
            {
                "pressure": {
                    "moderate_at": 0.8,
                    "high_at": 0.7,
                    "critical_at": 0.9,
                }
            }
        )


def test_system_and_current_input_priorities_cannot_be_downgraded():
    with pytest.raises(ValidationError, match="SYSTEM context priority"):
        ContextPolicyV1.model_validate(
            {"source_priorities": {"SYSTEM": "OPTIONAL", "USER_INPUT": "MANDATORY"}}
        )


def test_provider_model_capacity_resolves_from_persisted_catalog_metadata():
    snapshot = provider_model_pricing_snapshot(
        provider_model_id=uuid4(),
        provider_credential_id=uuid4(),
        provider="custom",
        model="deepseek-v4-flash",
        metadata={
            "catalog": {"context_window": 131072},
            "pricing": {
                "input_cost_per_1m_tokens": 0.1,
                "output_cost_per_1m_tokens": 0.2,
            },
        },
    )

    assert snapshot["context_window"] == 131072


def test_provider_model_capacity_resolves_from_preserved_provider_payload():
    snapshot = provider_model_pricing_snapshot(
        provider_model_id=uuid4(),
        provider_credential_id=uuid4(),
        provider="openrouter",
        model="provider/model",
        metadata={
            "provider_model_raw": {
                "top_provider": {"context_length": "65536"},
            }
        },
    )

    assert snapshot["context_window"] == 65536


def test_context_assembly_keeps_mandatory_input_and_only_recent_session_messages():
    policy = ContextPolicyV1.model_validate(
        {"session": {"max_messages": 1}}
    )
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="old user"),
            AIMessage(content="old answer"),
            HumanMessage(content="current user"),
        ],
        policy=policy,
    )

    assert [message.content for message in result.messages] == [
        "system",
        "old answer",
        "current user",
    ]
    assert result.snapshot.manifest["exclusions"][ContextSourceType.SESSION.value] == 1
    assert result.snapshot.manifest["exclusion_reasons"]["session_window"]["SESSION"] == 1
    assert [item.source_type for item in result.snapshot.contributions] == [
        ContextSourceType.SYSTEM,
        ContextSourceType.SESSION,
        ContextSourceType.USER_INPUT,
    ]


def test_current_user_contribution_uses_durable_message_id_when_available():
    message_id = uuid4()
    runtime = _runtime_context(input_message_id=message_id)
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="current user"),
        ],
        runtime_context=runtime,
    )

    current_input = next(
        item
        for item in result.snapshot.contributions
        if item.source_type == ContextSourceType.USER_INPUT
    )
    assert current_input.source_ref == str(message_id)


def test_context_contribution_preserves_tool_compaction_transformation():
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="current user"),
            ToolMessage(
                content='{"result":"compact"}',
                tool_call_id="tool-call-1",
                additional_kwargs={
                    "woobe_context": {
                        "source_type": "TOOL",
                        "source_ref": "tool-call-1",
                        "raw_units": 100,
                        "transformations": ["tool_output_compaction"],
                    }
                },
            ),
        ]
    )

    tool = next(
        item
        for item in result.snapshot.contributions
        if item.source_type == ContextSourceType.TOOL
    )
    assert tool.source_ref == "tool-call-1"
    assert tool.raw_units == 100
    assert tool.transformations == ("tool_output_compaction",)
    metrics = result.snapshot.manifest["metrics"]
    assert metrics["compaction_saving_units"] > 0
    assert metrics["compaction_ratio"] < 1


def test_knowledge_contribution_keeps_vector_and_chunk_provenance():
    runtime = _runtime_context(
        rag_metadata={
            "knowledge_version_id": "knowledge-v1",
            "vector_snapshot_id": "vector-v1",
        },
        context_rag_sources=[
            {"document_id": "doc-1", "chunk_id": "chunk-1", "score": 0.91}
        ],
    )
    result = _assemble(
        [
            SystemMessage(content="system"),
            SystemMessage(content="<context>retrieved fact</context>"),
            HumanMessage(content="current user"),
        ],
        runtime_context=runtime,
    )

    knowledge = next(
        item
        for item in result.snapshot.contributions
        if item.source_type == ContextSourceType.KNOWLEDGE
    )
    assert knowledge.source_ref == "vector-v1"
    assert knowledge.metadata["rag"]["knowledge_version_id"] == "knowledge-v1"
    assert knowledge.metadata["sources"][0]["chunk_id"] == "chunk-1"


def test_content_hash_dedup_keeps_latest_duplicate_and_records_selection_metrics():
    policy = ContextPolicyV1.model_validate(
        {
            "session": {"max_messages": 20},
            "deduplication": {"strategy": "content_hash", "sources": ["SESSION"]},
        }
    )
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="duplicate"),
            AIMessage(content="same answer"),
            HumanMessage(content="duplicate"),
            AIMessage(content="same answer"),
            HumanMessage(content="current"),
        ],
        policy=policy,
    )

    assert [message.content for message in result.messages] == [
        "system",
        "duplicate",
        "same answer",
        "current",
    ]
    manifest = result.snapshot.manifest
    assert manifest["exclusion_reasons"]["deduplicated"]["SESSION"] == 2
    assert manifest["metrics"]["raw_candidate_count"] == 6
    assert manifest["metrics"]["selected_count"] == 4
    assert 0 < manifest["metrics"]["selection_ratio"] < 1


def test_source_priority_ordering_is_versioned_and_recorded_in_manifest():
    policy = ContextPolicyV1.model_validate(
        {
            "ordering": {"strategy": "source_priority"},
            "source_priorities": {
                "SYSTEM": "MANDATORY",
                "USER_INPUT": "MANDATORY",
                "SESSION": "DYNAMIC",
                "CHECKPOINT": "HIGH",
                "MEMORY": "HIGH",
                "KNOWLEDGE": "HIGH",
                "TOOL": "DYNAMIC",
                "ARTIFACT": "DYNAMIC",
                "DELEGATION": "HIGH",
                "RUNTIME": "DYNAMIC",
            },
        }
    )
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="old user"),
            AIMessage(content="old answer"),
            SystemMessage(content="<context>knowledge</context>"),
            HumanMessage(content="current"),
        ],
        policy=policy,
    )

    assert [message.content for message in result.messages] == [
        "system",
        "current",
        "<context>knowledge</context>",
        "old user",
        "old answer",
    ]
    assert result.snapshot.manifest["ordering"]["strategy"] == "source_priority"
    assert result.snapshot.manifest["ordering"]["source_sequence"] == [
        "SYSTEM",
        "USER_INPUT",
        "KNOWLEDGE",
        "SESSION",
        "SESSION",
    ]


def test_source_budget_truncation_is_observable_in_context_health():
    policy = ContextPolicyV1.model_validate(
        {"knowledge": {"max_units": 128}}
    )
    result = _assemble(
        [
            SystemMessage(content="system"),
            SystemMessage(content=f"<context>{'k' * 900}</context>"),
            HumanMessage(content="current"),
        ],
        policy=policy,
    )

    knowledge = next(
        item
        for item in result.snapshot.contributions
        if item.source_type == ContextSourceType.KNOWLEDGE
    )
    assert "source_budget_truncate" in knowledge.transformations
    assert result.snapshot.manifest["metrics"]["truncation_count"] == 1
    assert result.snapshot.manifest["metrics"]["truncation_rate"] > 0
    assert "context_truncation_applied" in result.snapshot.manifest["health"]["warnings"]


def test_multimodal_input_is_not_reported_as_fully_comparable_text_context():
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(
                content=[
                    {"type": "text", "text": "describe this"},
                    {"type": "image_url", "image_url": {"url": "https://example.test/a.png"}},
                ]
            ),
        ]
    )

    current_input = next(
        item
        for item in result.snapshot.contributions
        if item.source_type == ContextSourceType.USER_INPUT
    )
    assert current_input.modality == "multimodal"
    assert result.snapshot.measurement_status == ContextMeasurementStatus.PARTIAL
    assert result.snapshot.utilization is None
    assert result.snapshot.manifest["modalities"]["aggregate_comparable"] is False
    assert "multimodal_units_not_fully_comparable" in result.snapshot.manifest["health"]["warnings"]


def test_source_share_is_recorded_from_materialized_context():
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="current user"),
        ]
    )

    sources = result.snapshot.manifest["sources"]
    total_share = sum(item["share"] for item in sources.values())
    assert total_share == pytest.approx(1.0)
    assert result.snapshot.manifest["metrics"]["source_share_measurement"] == "estimated"


def test_context_assembly_fails_when_mandatory_material_exceeds_model_budget():
    runtime_context = _runtime_context(
        model_capacity_units=40,
        reserved_output_units=0,
    )

    with pytest.raises(ContextBudgetExceeded, match="Mandatory context exceeds"):
        _assemble(
            [
                SystemMessage(content="s" * 120),
                HumanMessage(content="u" * 120),
            ],
            runtime_context=runtime_context,
        )


def test_reported_provider_usage_replaces_estimate_for_pressure_measurement():
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="hello"),
        ],
        runtime_context=_runtime_context(
            model_capacity_units=1000,
            reserved_output_units=100,
        ),
    )

    enriched = enrich_snapshot_with_reported_usage(result.snapshot, 850)

    assert enriched.usable_input_budget == 900
    assert enriched.reported_input_units == 850
    assert enriched.measurement_status == ContextMeasurementStatus.REPORTED
    assert enriched.pressure_status == ContextPressureStatus.CRITICAL
    assert enriched.utilization == pytest.approx(850 / 900)
    assert enriched.manifest["reported_input_units"] == 850
    assert enriched.manifest["metrics"]["reported_input_units"] == 850
    assert enriched.manifest["health"]["status"] == "critical"
