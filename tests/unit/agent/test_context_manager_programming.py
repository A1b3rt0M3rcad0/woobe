from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

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
from modules.agent.infra.context_management.manager_runtime import ContextManagerRunner
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
