from uuid import uuid4

from modules.observability.domain.entities import Trace
from modules.observability.infra.messaging.diagnostics_v2 import build
from modules.observability.infra.messaging.truthful_trace_projector import (
    _apply_runtime_dimensions,
)


def test_runtime_dimensions_are_preserved_from_payload():
    release_id = uuid4()
    trace = Trace(project_id=uuid4(), data={})

    _apply_runtime_dimensions(
        trace,
        {
            "execution_context": "production",
            "execution_strategy": "standard",
            "agent_release_id": str(release_id),
            "agent_release_version": "12",
            "llm_call_count": 3,
            "tool_call_count": 2,
        },
    )

    assert trace.data == {
        "execution_context": "production",
        "execution_strategy": "standard",
        "agent_release_id": str(release_id),
        "agent_release_version": "12",
        "llm_call_count": 3,
        "tool_call_count": 2,
    }


def test_runtime_dimensions_fall_back_to_diagnostics():
    trace = Trace(project_id=uuid4(), data={"existing": True})

    _apply_runtime_dimensions(
        trace,
        {
            "diagnostics": {
                "execution_context": "staging",
                "execution_strategy": "standard",
                "agent_release_id": str(uuid4()),
                "llm_call_count": 2,
            }
        },
    )

    assert trace.data is not None
    assert trace.data["existing"] is True
    assert trace.data["execution_context"] == "staging"
    assert trace.data["execution_strategy"] == "standard"
    assert trace.data["llm_call_count"] == 2


def test_diagnostics_preserve_execution_strategy_dimension():
    diagnostics = build(
        {
            "execution_strategy": "standard",
            "llm_calls": [],
            "tool_calls": [],
        }
    )

    assert diagnostics["execution_strategy"] == "standard"
