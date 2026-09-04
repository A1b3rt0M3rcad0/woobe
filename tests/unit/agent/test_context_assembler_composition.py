from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

from modules.agent.application.default_context_assembler import DefaultContextAssembler
from modules.agent.application.interfaces.context_assembler import (
    ContextAssemblyOutput,
    ContextAssemblyRequest,
)
from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_ask_agent_handler,
    build_ask_agent_use_case,
    build_internal_agent_runtime,
)
from shared.infra.config import Settings


def _assert_default_context_assembler(runtime) -> None:
    assert isinstance(
        getattr(runtime, "_context_assembler", None),
        DefaultContextAssembler,
    )


class _AlternateContextAssembler:
    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        raise AssertionError("Composition test does not execute Context Assembly")


class _FalsyAlternateContextAssembler(_AlternateContextAssembler):
    def __bool__(self) -> bool:
        return False


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


def test_public_agent_runtime_accepts_alternate_context_assembler() -> None:
    assembler = _AlternateContextAssembler()
    runtime, _transactions = build_ask_agent_use_case(
        Settings.model_validate({}),
        http_executor=MagicMock(),
        context_assembler=assembler,
    )

    assert runtime._context_assembler is assembler


def test_internal_network_runtime_accepts_alternate_context_assembler() -> None:
    assembler = _AlternateContextAssembler()
    runtime = build_internal_agent_runtime(
        Settings.model_validate({}),
        http_executor=MagicMock(),
        context_assembler=assembler,
    )

    assert runtime._context_assembler is assembler


def test_handler_composition_accepts_alternate_context_assembler() -> None:
    assembler = _AlternateContextAssembler()
    handler = build_ask_agent_handler(
        Settings.model_validate({}),
        http_executor=MagicMock(),
        context_assembler=assembler,
    )

    controller = cast(Any, handler).__self__
    assert controller._use_case._context_assembler is assembler


def test_composition_preserves_explicit_falsy_context_assembler() -> None:
    assembler = _FalsyAlternateContextAssembler()
    runtime, _transactions = build_ask_agent_use_case(
        Settings.model_validate({}),
        http_executor=MagicMock(),
        context_assembler=assembler,
    )

    assert runtime._context_assembler is assembler
