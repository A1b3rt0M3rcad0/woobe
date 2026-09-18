from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

from modules.agent.infra.context_management.managers.resolver import (
    ResolvedContextAssembler,
)
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
)
from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_ask_agent_handler,
    build_ask_agent_use_case,
    build_internal_agent_runtime,
)
from shared.infra.config import Settings


def _assert_registry_context_assembler(runtime) -> None:
    assert isinstance(
        getattr(runtime, "_context_assembler", None),
        ResolvedContextAssembler,
    )


class _AlternateContextAssembler:
    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        raise AssertionError("Composition test does not execute Context Assembly")


class _FalsyAlternateContextAssembler(_AlternateContextAssembler):
    def __bool__(self) -> bool:
        return False


def test_context_assembler_port_accepts_structural_implementations() -> None:
    assert isinstance(_AlternateContextAssembler(), ContextAssembler)


def test_public_agent_runtime_composition_wires_registry_dispatcher() -> None:
    runtime, _transactions = build_ask_agent_use_case(
        Settings.model_validate({}),
        http_executor=MagicMock(),
    )

    _assert_registry_context_assembler(runtime)


def test_default_composition_builds_snapshot_aware_dispatcher_with_configured_strategy(
    monkeypatch,
) -> None:
    from modules.agent.composition.factories import ask_agent_runtime_factory

    assembler = _AlternateContextAssembler()
    calls: list[str] = []

    def build_dispatcher(default_context_manager: str):
        calls.append(default_context_manager)
        return assembler

    monkeypatch.setattr(
        ask_agent_runtime_factory,
        "build_runtime_context_assembler",
        build_dispatcher,
    )

    settings = Settings.model_validate({"default_context_manager": "standard"})
    runtime, _transactions = ask_agent_runtime_factory.build_ask_agent_use_case(
        settings,
        http_executor=MagicMock(),
    )

    assert runtime._context_assembler is assembler
    assert calls == ["standard"]


def test_internal_network_agent_runtime_composition_wires_registry_dispatcher() -> None:
    runtime = build_internal_agent_runtime(
        Settings.model_validate({}),
        http_executor=MagicMock(),
    )

    _assert_registry_context_assembler(runtime)


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


def test_agent_entrypoint_preserves_alternate_context_assembler() -> None:
    from modules.agent.entrypoint import (
        build_internal_agent_runtime as build_entrypoint_agent_runtime,
    )

    assembler = _AlternateContextAssembler()
    runtime = build_entrypoint_agent_runtime(
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
