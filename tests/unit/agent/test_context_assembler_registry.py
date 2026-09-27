from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.context_assembler_registry import (
    ContextAssemblerDescriptor,
    ContextAssemblerRegistry,
    DuplicateContextAssemblerError,
    InvalidContextAssemblerFactoryError,
    InvalidDefaultContextManagerError,
    RegistryContextAssembler,
    UnknownContextAssemblerError,
    build_context_assembler,
    build_context_assembler_registry,
    canonicalize_context_assembler_runtime_config,
    list_context_assemblers,
)
from modules.agent.application.context_managers.standard import StandardContextAssembler
from modules.agent.application.interfaces.context_assembler import (
    DEFAULT_CONTEXT_ASSEMBLER_KEY,
    STANDARD_CONTEXT_ASSEMBLER_KEY,
    ContextAssembler,
    ContextAssemblerKey,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
    ContextCompactionOutput,
    ContextCompactionRequest,
    ContextInspectionOutput,
    ContextInspectionRequest,
    ContextManagerCapabilities,
)
from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from shared.contracts.errors import ValidationError


class _AlternateContextAssembler:
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
        return SimpleNamespace(messages=request.messages, snapshot=SimpleNamespace())


def _descriptor(
    key: ContextAssemblerKey,
    *,
    display_name: str = "Alternate Context Manager",
) -> ContextAssemblerDescriptor:
    return ContextAssemblerDescriptor(
        key=key,
        display_name=display_name,
        description="Alternate context manager used by tests.",
        behavior="Assembles test context deterministically.",
        recommended_for=("Test workloads.",),
        capabilities=("Returns the provided messages.",),
        limitations=("Test implementation only.",),
        configuration="Test configuration",
    )


def test_default_registry_exposes_only_named_standard_manager() -> None:
    registry = build_context_assembler_registry()
    descriptors = registry.list_descriptors()

    assert DEFAULT_CONTEXT_ASSEMBLER_KEY == ContextAssemblerKey("stdcm")
    assert STANDARD_CONTEXT_ASSEMBLER_KEY == ContextAssemblerKey("stdcm")
    assert [descriptor.key for descriptor in descriptors] == [
        ContextAssemblerKey("stdcm"),
    ]

    standard = descriptors[0]
    assert standard.display_name == "Standard Context Manager"
    assert standard.supports_skills is True
    assert standard.is_default is True


def test_catalog_has_no_version_or_strategy_alias_fields() -> None:
    descriptors = list_context_assemblers()

    assert len(descriptors) == 1
    standard = descriptors[0]
    assert standard["name"] == "stdcm"
    assert standard["is_default"] is True
    assert standard["supports_skills"] is True
    assert "compaction" in str(standard["behavior"]).lower()
    assert "version" not in standard
    assert "strategy_name" not in standard
    assert "strategy_version" not in standard
    assert "is_system_default_alias" not in standard


def test_build_context_assembler_resolves_stdcm_through_fresh_registry() -> None:
    first = build_context_assembler(ContextAssemblerKey("stdcm"))
    second = build_context_assembler(ContextAssemblerKey("stdcm"))

    assert isinstance(first, ContextAssembler)
    assert isinstance(second, ContextAssembler)
    assert first is not second


def test_registry_accepts_structural_context_manager_factory() -> None:
    key = ContextAssemblerKey("adaptive")
    registry = ContextAssemblerRegistry()
    registry.register(key, _AlternateContextAssembler, descriptor=_descriptor(key))

    assembler = registry.create(key)

    assert isinstance(assembler, ContextAssembler)
    assert isinstance(assembler, _AlternateContextAssembler)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("display_name", " "),
        ("description", " "),
        ("behavior", " "),
        ("configuration", " "),
        ("recommended_for", ()),
        ("capabilities", (" ",)),
        ("limitations", ()),
    ],
)
def test_descriptor_rejects_incomplete_product_metadata(field: str, value: object) -> None:
    key = ContextAssemblerKey("adaptive")
    values: dict[str, object] = {
        "key": key,
        "display_name": "Adaptive Context Manager",
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


def test_registry_can_make_any_registered_manager_the_system_default() -> None:
    key = ContextAssemblerKey("adaptive")
    registry = ContextAssemblerRegistry()
    registry.register(key, _AlternateContextAssembler, descriptor=_descriptor(key))

    registry.set_default(key)
    descriptor = registry.current_default()

    assert descriptor.key == key
    assert descriptor.is_default is True
    assert isinstance(registry.create(key), _AlternateContextAssembler)


def test_registry_rejects_unregistered_default() -> None:
    registry = ContextAssemblerRegistry()

    with pytest.raises(
        InvalidDefaultContextManagerError,
        match="not registered: adaptive",
    ):
        registry.set_default(ContextAssemblerKey("adaptive"))


def test_builder_rejects_unregistered_configured_default_manager() -> None:
    with pytest.raises(
        InvalidDefaultContextManagerError,
        match="not registered: adaptive",
    ):
        build_context_assembler_registry("adaptive")


def test_builder_rejects_versioned_default_manager_name() -> None:
    with pytest.raises(
        InvalidDefaultContextManagerError,
        match="registered Context Manager name",
    ):
        build_context_assembler_registry("stdcm:v1")


def test_registry_dispatcher_resolves_manager_by_runtime_name() -> None:
    key = ContextAssemblerKey("adaptive")
    registry = ContextAssemblerRegistry()
    registry.register(
        key,
        _AlternateContextAssembler,
        descriptor=_descriptor(key),
    )
    registry.set_default(key)
    dispatcher = RegistryContextAssembler(registry)
    request = ContextAssemblyRequest(
        messages=["hello"],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test-model",
        runtime_context=SimpleNamespace(context_assembler_name="adaptive"),
        policy=ContextPolicyV1(),
    )

    output = dispatcher.assemble(request)

    assert output.messages == ["hello"]


def test_new_agent_canonicalization_stores_only_manager_name() -> None:
    assert canonicalize_context_assembler_runtime_config(
        {"other": True},
        use_current_default_if_missing=True,
    ) == {
        "other": True,
        "context_assembler": {"name": "stdcm"},
    }


def test_runtime_config_without_selection_uses_stdcm() -> None:
    assert canonicalize_context_assembler_runtime_config({"other": True}) == {
        "other": True,
        "context_assembler": {"name": "stdcm"},
    }


def test_runtime_config_rejects_version_and_strategy_alias_fields() -> None:
    with pytest.raises(ValidationError, match="supports only the 'name' field"):
        canonicalize_context_assembler_runtime_config(
            {"context_assembler": {"name": "stdcm", "version": "v1"}}
        )


def test_runtime_config_rejects_unregistered_manager() -> None:
    with pytest.raises(
        ValidationError,
        match="Unsupported context assembler: missing",
    ):
        canonicalize_context_assembler_runtime_config(
            {"context_assembler": {"name": "missing"}}
        )


def test_registry_rejects_duplicate_identity() -> None:
    key = ContextAssemblerKey("adaptive")
    registry = ContextAssemblerRegistry()
    descriptor = _descriptor(key)
    registry.register(key, _AlternateContextAssembler, descriptor=descriptor)

    with pytest.raises(DuplicateContextAssemblerError, match="adaptive"):
        registry.register(key, _AlternateContextAssembler, descriptor=descriptor)


def test_registry_rejects_unknown_identity() -> None:
    registry = build_context_assembler_registry()

    with pytest.raises(UnknownContextAssemblerError, match="missing"):
        registry.create(ContextAssemblerKey("missing"))


def test_registry_rejects_incompatible_factory_result() -> None:
    key = ContextAssemblerKey("invalid")
    registry = ContextAssemblerRegistry()
    registry.register(
        key,
        lambda: object(),  # type: ignore[arg-type]
        descriptor=_descriptor(key),
    )

    with pytest.raises(InvalidContextAssemblerFactoryError, match="invalid"):
        registry.create(key)


def test_context_assembler_key_is_name_only() -> None:
    assert ContextAssemblerKey.parse(" stdcm ") == ContextAssemblerKey("stdcm")
    assert str(ContextAssemblerKey(" adaptive ")) == "adaptive"

    with pytest.raises(ValueError, match="plain name"):
        ContextAssemblerKey.parse("stdcm:v1")

    with pytest.raises(ValueError, match="must not be empty"):
        ContextAssemblerKey(" ")
