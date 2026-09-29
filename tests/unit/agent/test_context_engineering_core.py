from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from pydantic import ValidationError

from modules.agent.application.context_assembly import (
    ContextBudgetExceeded,
    assemble_context,
    enrich_snapshot_with_reported_usage,
    snapshot_to_dict,
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
        "knowledge_metadata": {},
        "knowledge_sources": [],
        "parent_invocation_id": None,
        "network_execution_id": None,
        "network_invocation_id": None,
        "network_node_id": None,
        "input_message_id": None,
        "run_id": uuid4(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _assemble(messages, *, policy=None, environment=None):
    return assemble_context(
        messages=messages,
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="openai",
        model="test-model",
        environment=environment or _runtime_context(),
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


@pytest.mark.parametrize(
    ("metadata", "configured_budget", "expected_budget"),
    [
        ({"context_window": 65536}, None, 60440),
        ({"catalog": {"context_window": 65536}}, None, 60440),
        ({"context_window": 0, "catalog": {"context_window": 65536}}, None, 60440),
        ({"provider_model_raw": {"top_provider": {"context_length": "65536"}}}, None, 60440),
        ({"context_window": 32000}, 64000, 26904),
        ({"max_output_tokens": 4096}, None, None),
        ({"max_output_tokens": 4096}, 16000, 16000),
    ],
)
def test_provider_capacity_reaches_persisted_context_budget(
    metadata, configured_budget, expected_budget
):
    pricing = provider_model_pricing_snapshot(
        provider_model_id=uuid4(),
        provider_credential_id=uuid4(),
        provider="custom",
        model="custom-model",
        metadata=metadata,
    )
    result = _assemble(
        [SystemMessage(content="system"), HumanMessage(content="hello")],
        policy=ContextPolicyV1.model_validate({
            "budget": {"max_input_units": configured_budget, "runtime_reserve_units": 1000},
        }),
        environment=_runtime_context(
            model_capacity_units=pricing["context_window"],
            reserved_output_units=4096,
        ),
    )
    persisted = snapshot_to_dict(enrich_snapshot_with_reported_usage(result.snapshot, 802))

    assert persisted["model_capacity_units"] == pricing["context_window"]
    assert persisted["usable_input_budget"] == expected_budget
    assert persisted["reported_input_units"] == 802
    if expected_budget is None:
        assert persisted["utilization"] is None
    else:
        assert persisted["utilization"] == pytest.approx(802 / expected_budget)


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


def test_session_window_counts_historical_tool_messages_without_losing_provenance():
    policy = ContextPolicyV1.model_validate(
        {"session": {"max_messages": 2}}
    )
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="old question"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "lookup",
                        "args": {"query": "old"},
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(content="old result", tool_call_id="call-1"),
            HumanMessage(content="current"),
        ],
        policy=policy,
    )

    assert not any(
        isinstance(message, HumanMessage) and message.content == "old question"
        for message in result.messages
    )
    assistant_index = next(
        index
        for index, message in enumerate(result.messages)
        if isinstance(message, AIMessage) and message.tool_calls
    )
    assert isinstance(result.messages[assistant_index + 1], ToolMessage)
    assert result.messages[assistant_index + 1].tool_call_id == "call-1"
    tool_contribution = next(
        item
        for item in result.snapshot.contributions
        if item.source_type == ContextSourceType.TOOL
    )
    assert tool_contribution.source_type == ContextSourceType.TOOL
    assert (
        result.snapshot.manifest["exclusion_reasons"]["session_window"]["SESSION"]
        == 1
    )


def test_current_user_contribution_uses_durable_message_id_when_available():
    message_id = uuid4()
    runtime = _runtime_context(input_message_id=message_id)
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="current user"),
        ],
        environment=runtime,
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
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tool-call-1",
                        "name": "lookup",
                        "args": {"query": "current"},
                        "type": "tool_call",
                    }
                ],
            ),
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
        knowledge_metadata={
            "knowledge_strategy": "rag",
            "knowledge_version_id": "knowledge-v1",
            "vector_snapshot_id": "vector-v1",
        },
        knowledge_sources=[
            {"document_id": "doc-1", "chunk_id": "chunk-1", "score": 0.91}
        ],
    )
    result = _assemble(
        [
            SystemMessage(content="system"),
            SystemMessage(content="<context>retrieved fact</context>"),
            HumanMessage(content="current user"),
        ],
        environment=runtime,
    )

    knowledge = next(
        item
        for item in result.snapshot.contributions
        if item.source_type == ContextSourceType.KNOWLEDGE
    )
    assert knowledge.source_ref == "vector-v1"
    assert knowledge.metadata["knowledge"]["knowledge_version_id"] == "knowledge-v1"
    # Preserve the historical RAG provenance alias for existing snapshots/readers.
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


def test_context_budget_metrics_report_fit_and_model_clamp():
    policy = ContextPolicyV1.model_validate(
        {
            "budget": {
                "max_input_units": 900,
                "runtime_reserve_units": 100,
            }
        }
    )
    result = _assemble(
        [SystemMessage(content="system"), HumanMessage(content="hello")],
        policy=policy,
        environment=_runtime_context(
            model_capacity_units=1000,
            reserved_output_units=200,
        ),
    )

    metrics = result.snapshot.manifest["metrics"]
    assert metrics["configured_input_budget_units"] == 900
    assert metrics["model_usable_input_units"] == 700
    assert metrics["effective_input_budget_units"] == 700
    assert metrics["budget_clamped"] is True
    assert metrics["budget_clamp_reason"] == "model_capacity"
    assert metrics["context_fit_status"] == "FIT"
    assert metrics["budget_reduction_units"] == 0
    assert metrics["context_preservation_ratio"] == pytest.approx(1.0)
    assert metrics["headroom_units"] == 700 - result.snapshot.estimated_input_units


def test_context_budget_drops_orphan_tool_messages_when_parent_tool_call_is_evicted():
    policy = ContextPolicyV1.model_validate(
        {"budget": {"max_input_units": 256}}
    )
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="old question"),
            AIMessage(
                content="assistant context " * 160,
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "lookup",
                        "args": {"query": "old"},
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="small result",
                tool_call_id="call-1",
            ),
            HumanMessage(content="current"),
        ],
        policy=policy,
        environment=_runtime_context(
            model_capacity_units=1000,
            reserved_output_units=0,
        ),
    )

    assert not any(isinstance(message, ToolMessage) for message in result.messages)
    assert not any(
        isinstance(message, AIMessage) and message.tool_calls
        for message in result.messages
    )
    assert (
        result.snapshot.manifest["exclusion_reasons"]["tool_protocol_orphan"]["TOOL"]
        == 1
    )


def test_context_assembly_preserves_streamed_assistant_tool_protocol_block():
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="current"),
            AIMessageChunk(
                content="",
                tool_calls=[
                    {
                        "id": "call-stream-1",
                        "name": "skills_activate",
                        "args": {"skill_version_id": "skill-v1"},
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content='{"success":true,"activated":true}',
                tool_call_id="call-stream-1",
            ),
        ],
    )

    assistant_index = next(
        index
        for index, message in enumerate(result.messages)
        if isinstance(message, AIMessageChunk) and message.tool_calls
    )
    assert isinstance(result.messages[assistant_index + 1], ToolMessage)
    assert result.messages[assistant_index + 1].tool_call_id == "call-stream-1"
    assert "tool_protocol_orphan" not in result.snapshot.manifest["exclusion_reasons"]
    assert result.snapshot.manifest["sources"]["TOOL"]["count"] == 1


def test_context_assembly_preserves_complete_parallel_tool_protocol_block():
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="old question"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-a",
                        "name": "lookup",
                        "args": {"query": "a"},
                        "type": "tool_call",
                    },
                    {
                        "id": "call-b",
                        "name": "lookup",
                        "args": {"query": "b"},
                        "type": "tool_call",
                    },
                ],
            ),
            ToolMessage(content="a", tool_call_id="call-a"),
            ToolMessage(content="b", tool_call_id="call-b"),
            HumanMessage(content="current"),
        ],
    )

    assistant_index = next(
        index
        for index, message in enumerate(result.messages)
        if isinstance(message, AIMessage) and message.tool_calls
    )
    assert [
        result.messages[assistant_index + 1].tool_call_id,
        result.messages[assistant_index + 2].tool_call_id,
    ] == ["call-a", "call-b"]


def test_context_budget_metrics_report_degraded_when_global_budget_reduces_context():
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="old " * 120),
            AIMessage(content="answer " * 120),
            HumanMessage(content="current"),
        ],
        environment=_runtime_context(
            model_capacity_units=90,
            reserved_output_units=10,
        ),
    )

    metrics = result.snapshot.manifest["metrics"]
    assert metrics["pre_budget_units"] > metrics["effective_input_budget_units"]
    assert metrics["context_fit_status"] == "DEGRADED"
    assert metrics["budget_reduction_units"] > 0
    assert 0 < metrics["context_preservation_ratio"] < 1
    assert result.snapshot.estimated_input_units <= result.snapshot.usable_input_budget


def test_context_assembly_fails_when_mandatory_material_exceeds_model_budget():
    runtime_context = _runtime_context(
        model_capacity_units=40,
        reserved_output_units=0,
    )

    with pytest.raises(ContextBudgetExceeded, match="Mandatory context exceeds") as error:
        _assemble(
            [
                SystemMessage(content="s" * 120),
                HumanMessage(content="u" * 120),
            ],
            environment=runtime_context,
        )

    failure = error.value.failure_context()
    assert failure["code"] == "CONTEXT_BUDGET_EXCEEDED"
    assert failure["context_fit_status"] == "UNFIT"
    assert failure["effective_budget_units"] == 40
    assert failure["mandatory_units"] > 40
    assert failure["provider_called"] is False


def test_reported_provider_usage_replaces_estimate_for_pressure_measurement():
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="hello"),
        ],
        environment=_runtime_context(
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
    assert enriched.manifest["metrics"]["headroom_units"] == 50
    assert enriched.manifest["metrics"]["headroom_ratio"] == pytest.approx(50 / 900)
    assert enriched.manifest["health"]["status"] == "critical"


def test_exposed_external_context_is_materialized_as_runtime_context() -> None:
    runtime = _runtime_context(
        external_context_contract={
            "name": {
                "schema": {"type": "string"},
                "required": True,
                    "model": {"expose": True},
                "description": "Preferred name of the current user",
            }
        },
        model_external_context={"name": "Alberto"},
    )
    result = _assemble(
        [
            SystemMessage(content="system"),
            HumanMessage(content="sabe meu nome?"),
        ],
        environment=runtime,
    )

    runtime_message = next(
        message
        for message in result.messages
        if message.additional_kwargs.get("woobe_context", {}).get("source_type")
        == "RUNTIME"
    )
    assert "Alberto" in runtime_message.content
    assert "Preferred name of the current user" in runtime_message.content

    contribution = next(
        item
        for item in result.snapshot.contributions
        if item.source_type == ContextSourceType.RUNTIME
    )
    assert contribution.source_ref == "external_context"
    assert contribution.metadata["selection_method"] == "runtime_external_context"
    assert result.snapshot.manifest["sources"]["RUNTIME"]["count"] == 1
