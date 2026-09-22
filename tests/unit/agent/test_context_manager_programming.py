from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.agent.application.context_assembler_registry import (
    build_context_assembler_registry,
)
from modules.agent.application.context_manager_sdk import (
    ContextManagerContext,
    ContextManagerOutcome,
)
from modules.agent.application.interfaces.context_assembler import ContextAssemblyRequest
from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.domain.context import ContextPriority, ContextSourceType
from modules.agent.infra.context_management.manager_runtime import (
    ContextManagerRunner,
    build_context_manager_context,
)
from modules.agent.infra.context_management.managers.resolver import (
    builtin_context_manager_names,
)


class _RecentOnlyManager:
    name = "recent-only"

    def assemble(
        self,
        ctx: ContextManagerContext,
    ) -> ContextManagerOutcome:
        ctx.candidates.recent_session(
            max_messages=1,
            max_units=None,
        )
        return ctx.complete()


def test_product_catalog_and_runtime_resolver_names_stay_in_parity() -> None:
    catalog_names = {
        descriptor.name
        for descriptor in build_context_assembler_registry().list_descriptors()
    }

    assert catalog_names == builtin_context_manager_names()


def test_custom_manager_programs_context_without_touching_runtime_mechanics() -> None:
    request = ContextAssemblyRequest(
        messages=[
            SystemMessage(content="System"),
            HumanMessage(content="old user"),
            AIMessage(content="old answer"),
            HumanMessage(content="current user"),
        ],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=SimpleNamespace(
            run_id=uuid4(),
            input_message_id=uuid4(),
            model_capacity_units=100_000,
            reserved_output_units=1_000,
            active_tool_definitions=None,
            context_selection_metadata=None,
            rag_metadata=None,
            context_rag_sources=None,
            parent_invocation_id=None,
            network_execution_id=None,
            network_invocation_id=None,
            network_node_id=None,
            skill_context=None,
        ),
        policy=ContextPolicyV1(),
    )

    output = ContextManagerRunner(_RecentOnlyManager()).assemble(request)

    contents = [message.content for message in output.messages]
    assert "old user" not in contents
    assert "old answer" in contents
    assert "current user" in contents
    assert output.snapshot.manifest["session_selection"] is None


class _InvalidManager:
    name = "invalid"

    def assemble(self, ctx: ContextManagerContext):
        return object()


def test_manager_context_uses_isolated_effective_policy() -> None:
    request = ContextAssemblyRequest(
        messages=[SystemMessage(content="System"), HumanMessage(content="current user")],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=SimpleNamespace(
            run_id=uuid4(),
            input_message_id=uuid4(),
            model_capacity_units=100_000,
            reserved_output_units=1_000,
            active_tool_definitions=None,
            context_selection_metadata=None,
            rag_metadata=None,
            context_rag_sources=None,
            parent_invocation_id=None,
            network_execution_id=None,
            network_invocation_id=None,
            network_node_id=None,
            skill_context=None,
            external_context_contract=None,
            model_external_context=None,
        ),
        policy=ContextPolicyV1(),
    )

    built = build_context_manager_context(request)
    built.candidates.recent_session(max_messages=1, max_units=128)
    outcome = built.complete()

    assert built.policy.session.max_messages == request.policy.session.max_messages
    assert built.policy.session.max_units == request.policy.session.max_units
    assert outcome.policy.session.max_messages == 1
    assert outcome.policy.session.max_units == 128
    assert request.policy.session.max_messages != 1
    assert request.policy.session.max_units != 128


def test_direct_policy_mutation_does_not_bypass_manager_primitives() -> None:
    request = ContextAssemblyRequest(
        messages=[SystemMessage(content="System"), HumanMessage(content="current user")],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=SimpleNamespace(skill_context=None),
        policy=ContextPolicyV1(),
    )

    built = build_context_manager_context(request)
    built.policy.session.max_messages = 1
    outcome = built.complete()

    assert outcome.policy.session.max_messages == request.policy.session.max_messages


def test_priority_and_pressure_primitives_program_effective_policy() -> None:
    request = ContextAssemblyRequest(
        messages=[SystemMessage(content="System"), HumanMessage(content="current user")],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=SimpleNamespace(skill_context=None),
        policy=ContextPolicyV1(),
    )

    built = build_context_manager_context(request)
    built.priorities.set(ContextSourceType.KNOWLEDGE, ContextPriority.HIGH)
    built.pressure.thresholds(moderate_at=0.25, high_at=0.60, critical_at=0.85)
    outcome = built.complete()

    assert outcome.policy.source_priorities[ContextSourceType.KNOWLEDGE] == ContextPriority.HIGH
    assert outcome.policy.pressure.moderate_at == 0.25
    assert outcome.policy.pressure.high_at == 0.60
    assert outcome.policy.pressure.critical_at == 0.85


def test_priority_primitive_preserves_mandatory_source_invariants() -> None:
    request = ContextAssemblyRequest(
        messages=[SystemMessage(content="System"), HumanMessage(content="current user")],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=SimpleNamespace(skill_context=None),
        policy=ContextPolicyV1(),
    )

    built = build_context_manager_context(request)

    with pytest.raises(ValueError, match="SYSTEM context priority must remain MANDATORY"):
        built.priorities.set(ContextSourceType.SYSTEM, ContextPriority.DYNAMIC)


def test_candidate_budget_and_pressure_primitives_validate_policy_constraints() -> None:
    request = ContextAssemblyRequest(
        messages=[SystemMessage(content="System"), HumanMessage(content="current user")],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=SimpleNamespace(skill_context=None),
        policy=ContextPolicyV1(),
    )

    built = build_context_manager_context(request)

    with pytest.raises(ValueError):
        built.candidates.recent_session(max_messages=0, max_units=None)

    with pytest.raises(ValueError):
        built.candidates.cap(ContextSourceType.KNOWLEDGE, 64)

    with pytest.raises(ValueError):
        built.budget.configure(max_input_units=128, runtime_reserve_units=0)

    with pytest.raises(ValueError):
        built.pressure.thresholds(
            moderate_at=0.80,
            high_at=0.70,
            critical_at=0.90,
        )


def test_capacity_primitive_tracks_effective_invocation_budget() -> None:
    request = ContextAssemblyRequest(
        messages=[SystemMessage(content="System"), HumanMessage(content="current user")],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=SimpleNamespace(
            skill_context=None,
            model_capacity_units=10_000,
            reserved_output_units=1_000,
        ),
        policy=ContextPolicyV1.model_validate(
            {
                "budget": {
                    "max_input_units": 12_000,
                    "runtime_reserve_units": 500,
                }
            }
        ),
    )

    built = build_context_manager_context(request)

    assert built.capacity.model_capacity_units == 10_000
    assert built.capacity.reserved_output_units == 1_000
    assert built.capacity.runtime_reserve_units == 500
    assert built.capacity.configured_input_budget_units == 12_000
    assert built.capacity.model_usable_input_units == 8_500
    assert built.capacity.usable_input_budget_units == 8_500
    assert built.capacity.budget_clamped is True

    built.budget.configure(max_input_units=4_000, runtime_reserve_units=500)

    assert built.capacity.configured_input_budget_units == 4_000
    assert built.capacity.usable_input_budget_units == 4_000
    assert built.capacity.budget_clamped is False



def test_inventory_primitive_exposes_aggregate_sources_without_raw_messages() -> None:
    request = ContextAssemblyRequest(
        messages=[
            SystemMessage(content="System"),
            HumanMessage(content="old user"),
            AIMessage(content="old answer"),
            SystemMessage(content="<context>knowledge</context>"),
            HumanMessage(content="current user"),
        ],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=SimpleNamespace(
            skill_context=None,
            model_capacity_units=100_000,
            reserved_output_units=1_000,
            active_tool_definitions=[
                {"type": "function", "function": {"name": "lookup"}}
            ],
            external_context_contract=None,
            model_external_context=None,
            parent_invocation_id=None,
        ),
        policy=ContextPolicyV1(),
    )

    built = build_context_manager_context(request)

    assert built.inventory.count(ContextSourceType.SYSTEM) == 2
    assert built.inventory.count(ContextSourceType.SESSION) == 2
    assert built.inventory.count(ContextSourceType.KNOWLEDGE) == 1
    assert built.inventory.count(ContextSourceType.USER_INPUT) == 1
    assert built.inventory.contains(ContextSourceType.TOOL) is False
    assert built.inventory.total_count == 6
    assert built.inventory.total_units > 0
    assert ContextSourceType.SESSION in built.inventory.sources

def test_manager_runner_rejects_non_sdk_outcomes() -> None:
    request = ContextAssemblyRequest(
        messages=[SystemMessage(content="System"), HumanMessage(content="current user")],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test",
        runtime_context=SimpleNamespace(
            run_id=uuid4(),
            input_message_id=uuid4(),
            model_capacity_units=100_000,
            reserved_output_units=1_000,
            active_tool_definitions=None,
            context_selection_metadata=None,
            rag_metadata=None,
            context_rag_sources=None,
            parent_invocation_id=None,
            network_execution_id=None,
            network_invocation_id=None,
            network_node_id=None,
            skill_context=None,
            external_context_contract=None,
            model_external_context=None,
        ),
        policy=ContextPolicyV1(),
    )

    try:
        ContextManagerRunner(_InvalidManager()).assemble(request)
    except TypeError as exc:
        assert "ContextManagerOutcome" in str(exc)
    else:
        raise AssertionError("invalid Context Manager outcome was accepted")
