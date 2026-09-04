from __future__ import annotations

import pytest

from modules.agent.application.default_context_assembler import DefaultContextAssembler
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
)
from modules.agent.composition.context_assembler_registry import (
    DEFAULT_CONTEXT_ASSEMBLER_KEY,
    ContextAssemblerKey,
    ContextAssemblerRegistry,
    DuplicateContextAssemblerError,
    InvalidContextAssemblerFactoryError,
    UnknownContextAssemblerError,
    build_context_assembler,
    build_context_assembler_registry,
)


class _AlternateContextAssembler:
    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        raise AssertionError("Registry test does not execute Context Assembly")


def test_default_registry_resolves_versioned_default_assembler() -> None:
    registry = build_context_assembler_registry()

    assembler = registry.create(DEFAULT_CONTEXT_ASSEMBLER_KEY)

    assert DEFAULT_CONTEXT_ASSEMBLER_KEY == ContextAssemblerKey("default", "v1")
    assert str(DEFAULT_CONTEXT_ASSEMBLER_KEY) == "default:v1"
    assert isinstance(assembler, DefaultContextAssembler)
    assert isinstance(assembler, ContextAssembler)


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
