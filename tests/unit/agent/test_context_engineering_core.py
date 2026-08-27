from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
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
    ContextSourceType,
)


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

    policy = ContextPolicyV1.model_validate(runtime["context"])
    assert context_policy_hash(policy) == context_policy_hash(runtime["context"])


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
    assert [item.source_type for item in result.snapshot.contributions] == [
        ContextSourceType.SYSTEM,
        ContextSourceType.SESSION,
        ContextSourceType.USER_INPUT,
    ]


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
