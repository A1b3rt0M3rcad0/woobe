from __future__ import annotations

from unittest.mock import MagicMock

from modules.agent.application.default_context_assembler import DefaultContextAssembler
from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_ask_agent_use_case,
    build_internal_agent_runtime,
)
from shared.infra.config import Settings


def _assert_default_context_assembler(runtime) -> None:
    assert isinstance(
        getattr(runtime, "_context_assembler", None),
        DefaultContextAssembler,
    )


def test_public_agent_runtime_composition_wires_default_context_assembler() -> None:
    runtime, _transactions = build_ask_agent_use_case(
        Settings.model_validate({}),
        http_executor=MagicMock(),
    )

    _assert_default_context_assembler(runtime)


def test_internal_network_agent_runtime_composition_wires_default_context_assembler() -> None:
    runtime = build_internal_agent_runtime(
        Settings.model_validate({}),
        http_executor=MagicMock(),
    )

    _assert_default_context_assembler(runtime)
