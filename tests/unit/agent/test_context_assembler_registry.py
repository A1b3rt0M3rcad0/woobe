from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.context_assembler_registry import (
    ContextAssemblerDescriptor,
    ContextAssemblerRegistry,
    DuplicateContextAssemblerError,
    InvalidContextAssemblerFactoryError,
    RegistryContextAssembler,
    UnknownContextAssemblerError,
    build_context_assembler,
    build_context_assembler_registry,
    canonicalize_context_assembler_runtime_config,
    list_context_assemblers,
)
from modules.agent.application.default_context_assembler import DefaultContextAssembler
from modules.agent.application.interfaces.context_assembler import (
    DEFAULT_CONTEXT_ASSEMBLER_KEY,
    ContextAssembler,
    ContextAssemblerKey,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
)
from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from shared.contracts.errors import ValidationError


class _AlternateContextAssembler:
    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        return SimpleNamespace(messages=request.messages, snapshot=SimpleNamespace())


def test_default_registry_resolves_versioned_default_assembler() -> None:
    registry = build_context_assembler_registry()

    assembler = registry.create(DEFAULT_CONTEXT_ASSEMBLER_KEY)

    assert DEFAULT_CONTEXT_ASSEMBLER_KEY == ContextAssemblerKey("default", "v1")
    assert str(DEFAULT_CONTEXT_ASSEMBLER_KEY) == "default:v1"
    assert isinstance(assembler, DefaultContextAssembler)
    assert isinstance(assembler, ContextAssembler)


def test_default_registry_exposes_product_metadata() -> None:
    descriptors = list_context_assemblers()

    assert descriptors == [
        {
            "name": "default",
            "version": "v1",
            "display_name": "Default Context",
            "description": (
                "Balanced deterministic context assembly for general-purpose Agent execution."
            ),
            "behavior": (
                "Preserves mandatory inputs, applies Context Policy v1 budgets and priorities, "
                "trims context under pressure, and records provenance in the Context Snapshot."
            ),
            "is_default": True,
        }
    ]


def test_build_context_assembler_resolves_through_fresh_registry() -> None:
    first = build_context_assembler(DEFAULT_CONTEXT_ASSEMBLER_KEY)
    second = build_context_assembler(DEFAULT_CONTEXT_ASSEMBLER_KEY)

    assert isinstance(first, DefaultContextAssembler)
    assert isinstance(second, DefaultContextAssembler)
    assert first is not second


def test_registry_accepts_structural_context_assembler_factory() -> None:
    key = ContextAssemblerKey("alternate", "v1")
    registry = ContextAssemblerRegistry()
    registry.register(key, _AlternateContextAssembler)

    assembler = registry.create(key)

    assert isinstance(assembler, ContextAssembler)
    assert isinstance(assembler, _AlternateContextAssembler)


def test_registry_dispatcher_resolves_manager_from_invocation_runtime_context() -> None:
    key = ContextAssemblerKey("alternate", "v1")
    registry = ContextAssemblerRegistry()
    registry.register(
        key,
        _AlternateContextAssembler,
        descriptor=ContextAssemblerDescriptor(
            key=key,
            display_name="Alternate",
            description="test",
            behavior="test",
        ),
    )
    dispatcher = RegistryContextAssembler(registry)
    request = ContextAssemblyRequest(
        messages=["hello"],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test-model",
        runtime_context=SimpleNamespace(
            context_assembler_name="alternate",
            context_assembler_version="v1",
        ),
        policy=ContextPolicyV1(),
    )

    output = dispatcher.assemble(request)

    assert output.messages == ["hello"]


def test_runtime_config_canonicalization_freezes_default_identity() -> None:
    assert canonicalize_context_assembler_runtime_config({"other": True}) == {
        "other": True,
        "context_assembler": {"name": "default", "version": "v1"},
    }


def test_runtime_config_rejects_unregistered_identity() -> None:
    with pytest.raises(ValidationError, match="Unsupported context assembler: missing:v1"):
        canonicalize_context_assembler_runtime_config(
            {"context_assembler": {"name": "missing", "version": "v1"}}
        )


def test_registry_rejects_duplicate_identity() -> None:
    key = ContextAssemblerKey("adaptive", "v1")
    registry = ContextAssemblerRegistry()
    registry.register(key, _AlternateContextAssembler)

    with pytest.raises(DuplicateContextAssemblerError, match="adaptive:v1"):
        registry.register(key, _AlternateContextAssembler)


def test_registry_rejects_unknown_identity() -> None:
    registry = ContextAssemblerRegistry()

    with pytest.raises(UnknownContextAssemblerError, match="missing:v3"):
        registry.create(ContextAssemblerKey("missing", "v3"))


def test_registry_rejects_incompatible_factory_result() -> None:
    key = ContextAssemblerKey("invalid", "v1")
    registry = ContextAssemblerRegistry()
    registry.register(key, lambda: object())  # type: ignore[arg-type]

    with pytest.raises(InvalidContextAssemblerFactoryError, match="invalid:v1"):
        registry.create(key)


@pytest.mark.parametrize(
    ("name", "version", "message"),
    [
        (" ", "v1", "name"),
        ("default", " ", "version"),
    ],
)
def test_context_assembler_key_rejects_empty_identity_parts(
    name: str,
    version: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ContextAssemblerKey(name=name, version=version)


def test_context_assembler_key_normalizes_surrounding_whitespace() -> None:
    key = ContextAssemblerKey("  adaptive  ", "  v2 ")

    assert key == ContextAssemblerKey("adaptive", "v2")
    assert str(key) == "adaptive:v2"
