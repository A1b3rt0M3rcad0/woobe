from __future__ import annotations

import pytest

from modules.agent.application.context_manager_registry import (
    ContextAssemblerDescriptor,
    ContextAssemblerRegistry,
    DuplicateContextAssemblerError,
    InvalidDefaultContextManagerError,
    UnknownContextAssemblerError,
    build_context_assembler_registry,
    canonicalize_context_assembler_runtime_config,
    list_context_assemblers,
)
from modules.agent.application.interfaces.context_assembler import (
    DEFAULT_CONTEXT_MANAGER,
    ContextAssemblerSelection,
    context_assembler_selection_from_runtime_config,
    normalize_context_manager_name,
)
from shared.contracts.errors import ValidationError


def _descriptor(
    name: str = "adaptive",
    *,
    is_default: bool = False,
) -> ContextAssemblerDescriptor:
    return ContextAssemblerDescriptor(
        name=name,
        display_name="Adaptive Context Manager",
        description="Adaptive context manager used by tests.",
        behavior="Selects test context deterministically.",
        recommended_for=("Test workloads.",),
        capabilities=("Selects context.",),
        limitations=("Test implementation only.",),
        configuration="Test configuration",
        is_default=is_default,
    )


def test_default_registry_exposes_single_canonical_standard_manager() -> None:
    registry = build_context_assembler_registry()
    descriptors = registry.list_descriptors()

    assert [descriptor.name for descriptor in descriptors] == ["standard", "adaptive"]
    standard = descriptors[0]
    adaptive = descriptors[1]
    assert standard.is_default is True
    assert standard.supports_skills is True
    assert adaptive.is_default is False
    assert adaptive.supports_skills is True
    assert registry.current_default() == standard


def test_catalog_exposes_unversioned_backend_owned_metadata() -> None:
    descriptors = list_context_assemblers()

    assert len(descriptors) == 2
    standard = next(item for item in descriptors if item["name"] == "standard")
    adaptive = next(item for item in descriptors if item["name"] == "adaptive")
    assert standard["name"] == "standard"
    assert standard["display_name"] == "Standard Context Manager"
    assert standard["supports_skills"] is True
    assert standard["is_default"] is True
    assert "version" not in standard
    assert "strategy_name" not in standard
    assert "strategy_version" not in standard
    assert "is_system_default_alias" not in standard
    assert adaptive["display_name"] == "Adaptive Context Manager"
    assert adaptive["supports_skills"] is True
    assert adaptive["is_default"] is False


def test_registry_is_metadata_only_and_rejects_duplicate_identity() -> None:
    registry = ContextAssemblerRegistry()
    descriptor = _descriptor()
    registry.register(descriptor)

    with pytest.raises(DuplicateContextAssemblerError, match="adaptive"):
        registry.register(descriptor)


def test_registry_rejects_unknown_identity() -> None:
    registry = ContextAssemblerRegistry()

    with pytest.raises(UnknownContextAssemblerError, match="missing"):
        registry.get("missing")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", " "),
        ("display_name", " "),
        ("description", " "),
        ("behavior", " "),
        ("configuration", " "),
        ("recommended_for", ()),
        ("capabilities", (" ",)),
        ("limitations", ()),
    ],
)
def test_descriptor_rejects_incomplete_product_metadata(
    field: str,
    value: object,
) -> None:
    values: dict[str, object] = {
        "name": "adaptive",
        "display_name": "Adaptive",
        "description": "Description",
        "behavior": "Behavior",
        "recommended_for": ("General use",),
        "capabilities": ("Capability",),
        "limitations": ("Limitation",),
        "configuration": "Configuration",
    }
    values[field] = value

    with pytest.raises(ValueError, match=field):
        ContextAssemblerDescriptor(**values)  # type: ignore[arg-type]


def test_builder_can_select_adaptive_as_configured_default_manager() -> None:
    registry = build_context_assembler_registry("adaptive")

    assert registry.current_default().name == "adaptive"
    assert registry.get("standard").is_default is False


def test_builder_rejects_unregistered_configured_default_manager() -> None:
    with pytest.raises(
        InvalidDefaultContextManagerError,
        match="exactly one default",
    ):
        build_context_assembler_registry("missing")


def test_new_snapshot_canonicalization_persists_only_stable_name() -> None:
    assert canonicalize_context_assembler_runtime_config(
        {"other": True},
        use_current_default_if_missing=True,
    ) == {
        "other": True,
        "context_assembler": {"name": "standard"},
    }


def test_missing_selection_keeps_historical_standard_fallback() -> None:
    assert canonicalize_context_assembler_runtime_config({"other": True}) == {
        "other": True,
        "context_assembler": {"name": "standard"},
    }


@pytest.mark.parametrize(
    "selection",
    [
        {"name": "standard"},
        {"name": "stdcm", "version": "v1"},
        {"name": "stdcm", "version": "v2"},
        {"name": "default", "version": "v1"},
        {
            "name": "default",
            "version": "v1",
            "strategy_name": "stdcm",
            "strategy_version": "v2",
        },
    ],
)
def test_legacy_standard_selections_canonicalize_to_standard(
    selection: dict[str, str],
) -> None:
    result = canonicalize_context_assembler_runtime_config(
        {"context_assembler": selection}
    )

    assert result["context_assembler"] == {"name": "standard"}


def test_historical_frozen_strategy_name_is_honored_by_parser() -> None:
    selection = context_assembler_selection_from_runtime_config(
        {
            "context_assembler": {
                "name": "default",
                "version": "v1",
                "strategy_name": "adaptive",
                "strategy_version": "v1",
            }
        }
    )

    assert selection == ContextAssemblerSelection("adaptive")


def test_runtime_config_rejects_unregistered_manager() -> None:
    with pytest.raises(
        ValidationError,
        match="Unsupported Context Manager: missing",
    ):
        canonicalize_context_assembler_runtime_config(
            {"context_assembler": {"name": "missing"}}
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" standard ", "standard"),
        ("stdcm", "standard"),
        ("default", "standard"),
        (" Adaptive ", "adaptive"),
    ],
)
def test_context_manager_name_normalization(value: str, expected: str) -> None:
    assert normalize_context_manager_name(value) == expected


def test_context_manager_name_rejects_empty_identity() -> None:
    with pytest.raises(ValueError, match="name"):
        normalize_context_manager_name(" ")
