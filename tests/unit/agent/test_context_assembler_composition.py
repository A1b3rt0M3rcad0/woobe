from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

from modules.agent.application.context_manager_registry import RegistryContextManager
from modules.agent.application.interfaces.context_manager import (
    ContextManager,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
    ContextCompactionOutput,
    ContextCompactionRequest,
    ContextInspectionOutput,
    ContextInspectionRequest,
    ContextManagerCapabilities,
)
from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_ask_agent_handler,
    build_ask_agent_use_case,
    build_internal_agent_runtime,
)
from shared.infra.config import Settings


def _assert_registry_context_manager(runtime) -> None:
    assert isinstance(
        getattr(runtime, "_context_manager", None),
        RegistryContextManager,
    )


class _AlternateContextManager:
    def inspect(self, request: ContextInspectionRequest) -> ContextInspectionOutput:
        return ContextInspectionOutput(
            message_count=len(request.messages),
            contribution_count=len(request.contributions),
            estimated_input_units=0,
            usable_input_units=None,
            utilization=None,
            pressure="UNKNOWN",
        )

    async def compact(
        self,
        request: ContextCompactionRequest,
        capabilities: ContextManagerCapabilities,
    ) -> ContextCompactionOutput:
        del request, capabilities
        return ContextCompactionOutput(changed=False)

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        raise AssertionError("Composition test does not execute Context Assembly")


class _FalsyAlternateContextManager(_AlternateContextManager):
    def __bool__(self) -> bool:
        return False


def test_context_manager_port_accepts_structural_implementations() -> None:
    assert isinstance(_AlternateContextManager(), ContextManager)


def test_public_agent_runtime_composition_wires_registry_dispatcher() -> None:
    runtime, _transactions = build_ask_agent_use_case(
        Settings.model_validate({}),
        http_executor=MagicMock(),
    )

    _assert_registry_context_manager(runtime)


def test_default_composition_builds_snapshot_aware_dispatcher_with_configured_strategy(
    monkeypatch,
) -> None:
    from modules.agent.composition.factories import ask_agent_runtime_factory

    assembler = _AlternateContextManager()
    calls: list[str] = []

    def build_dispatcher(default_context_manager: str):
        calls.append(default_context_manager)
        return assembler

    monkeypatch.setattr(
        ask_agent_runtime_factory,
        "build_runtime_context_manager",
        build_dispatcher,
    )

    settings = Settings.model_validate({"default_context_manager": "stdcm"})
    runtime, _transactions = ask_agent_runtime_factory.build_ask_agent_use_case(
        settings,
        http_executor=MagicMock(),
    )

    assert runtime._context_manager is assembler
    assert calls == ["stdcm"]


def test_internal_network_agent_runtime_composition_wires_registry_dispatcher() -> None:
    runtime = build_internal_agent_runtime(
        Settings.model_validate({}),
        http_executor=MagicMock(),
    )

    _assert_registry_context_manager(runtime)


def test_public_agent_runtime_accepts_alternate_context_manager() -> None:
    assembler = _AlternateContextManager()
    runtime, _transactions = build_ask_agent_use_case(
        Settings.model_validate({}),
        http_executor=MagicMock(),
        context_assembler=assembler,
    )

    assert runtime._context_manager is assembler


def test_internal_network_runtime_accepts_alternate_context_manager() -> None:
    assembler = _AlternateContextManager()
    runtime = build_internal_agent_runtime(
        Settings.model_validate({}),
        http_executor=MagicMock(),
        context_assembler=assembler,
    )

    assert runtime._context_manager is assembler


def test_agent_entrypoint_preserves_alternate_context_manager() -> None:
    from modules.agent.entrypoint import (
        build_internal_agent_runtime as build_entrypoint_agent_runtime,
    )

    assembler = _AlternateContextManager()
    runtime = build_entrypoint_agent_runtime(
        Settings.model_validate({}),
        http_executor=MagicMock(),
        context_assembler=assembler,
    )

    assert runtime._context_manager is assembler


def test_handler_composition_accepts_alternate_context_manager() -> None:
    assembler = _AlternateContextManager()
    handler = build_ask_agent_handler(
        Settings.model_validate({}),
        http_executor=MagicMock(),
        context_assembler=assembler,
    )

    controller = cast(Any, handler).__self__
    assert controller._use_case._context_manager is assembler


def test_composition_preserves_explicit_falsy_context_manager() -> None:
    assembler = _FalsyAlternateContextManager()
    runtime, _transactions = build_ask_agent_use_case(
        Settings.model_validate({}),
        http_executor=MagicMock(),
        context_assembler=assembler,
    )

    assert runtime._context_manager is assembler
