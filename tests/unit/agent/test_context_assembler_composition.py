from __future__ import annotations

from unittest.mock import MagicMock

from modules.agent.application.default_context_assembler import DefaultContextAssembler
from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_ask_agent_use_case,
)
from shared.infra.config import Settings


def test_agent_runtime_composition_wires_default_context_assembler() -> None:
    runtime, _transactions = build_ask_agent_use_case(
        Settings.model_validate({}),
        http_executor=MagicMock(),
    )

    assert isinstance(
        getattr(runtime, "_context_assembler", None),
        DefaultContextAssembler,
    )
