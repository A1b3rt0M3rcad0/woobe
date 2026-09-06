from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import woobe_workers.composition.network_agent_runtime as network_agent_runtime
from woobe_workers.composition.network_agent_runtime import ProjectRAIAgentInvoker


@pytest.mark.asyncio
async def test_network_bridge_preserves_agent_skill_snapshot_override(monkeypatch) -> None:
    captured = {}
    trace_id = uuid4()

    class Runtime:
        async def execute(self, input_dto):
            captured["snapshot_override"] = input_dto.snapshot_override
            captured["source"] = input_dto.metadata["source"]
            return SimpleNamespace(
                answer="ok",
                session_id=None,
                trace_id=trace_id,
                provider="openai",
                model="test",
                usage=None,
                tool_calls=[],
                sources=[],
                parsed_output=None,
                output_parse_error=None,
            )

    monkeypatch.setattr(
        network_agent_runtime,
        "build_internal_agent_runtime",
        lambda *_args, **_kwargs: Runtime(),
    )

    skill_id = uuid4()
    skill_version_id = uuid4()
    snapshot_override = {
        "provider": "openai",
        "model": "test",
        "runtime_config": {
            "context_assembler": {"name": "stdcm", "version": "v2"},
            "skills": {
                "bindings": [
                    {
                        "skill_id": str(skill_id),
                        "skill_version_id": str(skill_version_id),
                        "enabled": True,
                    }
                ],
                "snapshots": [
                    {
                        "skill_id": str(skill_id),
                        "skill_version_id": str(skill_version_id),
                        "version": "1.0.0",
                    }
                ],
            },
        },
    }

    invoker = ProjectRAIAgentInvoker(SimpleNamespace(), object())
    result = await invoker.invoke(
        project_id=uuid4(),
        agent_id=uuid4(),
        release_id=None,
        snapshot_override=snapshot_override,
        message="Quanto é 1 + 1?",
        agent_session_id=None,
        execution_context="playground",
        internal_tools=[],
        network_context={
            "network_id": str(uuid4()),
            "network_session_id": str(uuid4()),
            "network_execution_id": str(uuid4()),
            "network_invocation_id": str(uuid4()),
            "network_node_id": str(uuid4()),
            "depth": 0,
        },
    )

    assert result.answer == "ok"
    assert captured["source"] == "network_runtime"
    assert captured["snapshot_override"] == snapshot_override
