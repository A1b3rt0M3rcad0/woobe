from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.context_manager_registry import (
    ContextManagerDescriptor,
    ContextManagerRegistry,
    DuplicateContextManagerError,
    InvalidContextManagerFactoryError,
    InvalidDefaultContextManagerError,
    RegistryContextManager,
    UnknownContextManagerError,
    build_context_manager,
    build_context_manager_registry,
    canonicalize_context_manager_runtime_config,
    list_context_managers,
)
from modules.agent.application.context_managers.standard import StandardContextManager
from modules.agent.application.interfaces.context_manager import (
    DEFAULT_CONTEXT_MANAGER_KEY,
    STANDARD_CONTEXT_MANAGER_KEY,
    ContextManager,
    ContextManagerKey,
    ContextInvocationEnvironment,
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
        return SimpleNamespace(messages=request.messages, snapshot=SimpleNamespace())


def _descriptor(
    key: ContextManagerKey,
    *,
    display_name: str = "Alternate Context Manager",
) -> ContextManagerDescriptor:
    return ContextManagerDescriptor(
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
    registry = build_context_manager_registry()
    descriptors = registry.list_descriptors()

    assert DEFAULT_CONTEXT_MANAGER_KEY == ContextManagerKey("stdcm")
    assert STANDARD_CONTEXT_MANAGER_KEY == ContextManagerKey("stdcm")
    assert [descriptor.key for descriptor in descriptors] == [
        ContextManagerKey("stdcm"),
    ]

    standard = descriptors[0]
    assert standard.display_name == "Standard Context Manager"
    assert standard.supports_skills is True
    assert standard.is_default is True


def test_catalog_has_no_version_or_strategy_alias_fields() -> None:
    descriptors = list_context_managers()

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


def test_build_context_manager_resolves_stdcm_through_fresh_registry() -> None:
    first = build_context_manager(ContextManagerKey("stdcm"))
    second = build_context_manager(ContextManagerKey("stdcm"))

    assert isinstance(first, ContextManager)
    assert isinstance(second, ContextManager)
    assert first is not second


def test_registry_accepts_structural_context_manager_factory() -> None:
    key = ContextManagerKey("adaptive")
    registry = ContextManagerRegistry()
    registry.register(key, _AlternateContextManager, descriptor=_descriptor(key))

    assembler = registry.create(key)

    assert isinstance(assembler, ContextManager)
    assert isinstance(assembler, _AlternateContextManager)


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
    key = ContextManagerKey("adaptive")
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
        ContextManagerDescriptor(**values)  # type: ignore[arg-type]


def test_registry_can_make_any_registered_manager_the_system_default() -> None:
    key = ContextManagerKey("adaptive")
    registry = ContextManagerRegistry()
    registry.register(key, _AlternateContextManager, descriptor=_descriptor(key))

    registry.set_default(key)
    descriptor = registry.current_default()

    assert descriptor.key == key
    assert descriptor.is_default is True
    assert isinstance(registry.create(key), _AlternateContextManager)


def test_registry_rejects_unregistered_default() -> None:
    registry = ContextManagerRegistry()

    with pytest.raises(
        InvalidDefaultContextManagerError,
        match="not registered: adaptive",
    ):
        registry.set_default(ContextManagerKey("adaptive"))


def test_builder_rejects_unregistered_configured_default_manager() -> None:
    with pytest.raises(
        InvalidDefaultContextManagerError,
        match="not registered: adaptive",
    ):
        build_context_manager_registry("adaptive")


def test_builder_rejects_versioned_default_manager_name() -> None:
    with pytest.raises(
        InvalidDefaultContextManagerError,
        match="registered Context Manager name",
    ):
        build_context_manager_registry("stdcm:legacy")


def test_registry_dispatcher_resolves_manager_by_runtime_name() -> None:
    key = ContextManagerKey("adaptive")
    registry = ContextManagerRegistry()
    registry.register(
        key,
        _AlternateContextManager,
        descriptor=_descriptor(key),
    )
    registry.set_default(key)
    dispatcher = RegistryContextManager(registry)
    request = ContextAssemblyRequest(
        messages=["hello"],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test-model",
        environment=ContextInvocationEnvironment(context_manager_name="adaptive"),
        policy=ContextPolicyV1(),
    )

    output = dispatcher.assemble(request)

    assert output.messages == ["hello"]


def test_new_agent_canonicalization_stores_only_manager_name() -> None:
    assert canonicalize_context_manager_runtime_config(
        {"other": True},
        use_current_default_if_missing=True,
    ) == {
        "other": True,
        "context_manager": {"name": "stdcm"},
    }


def test_runtime_config_without_selection_uses_stdcm() -> None:
    assert canonicalize_context_manager_runtime_config({"other": True}) == {
        "other": True,
        "context_manager": {"name": "stdcm"},
    }


def test_legacy_context_assembler_selection_is_canonicalized() -> None:
    assert canonicalize_context_manager_runtime_config(
        {"context_assembler": {"name": "stdcm"}}
    ) == {
        "context_manager": {"name": "stdcm"},
    }


def test_runtime_config_rejects_version_and_strategy_alias_fields() -> None:
    with pytest.raises(ValidationError, match="supports only the 'name' field"):
        canonicalize_context_manager_runtime_config(
            {"context_manager": {"name": "stdcm", "version": "v1"}}
        )


def test_runtime_config_rejects_unregistered_manager() -> None:
    with pytest.raises(
        ValidationError,
        match="Unsupported context assembler: missing",
    ):
        canonicalize_context_manager_runtime_config(
            {"context_manager": {"name": "missing"}}
        )


def test_registry_rejects_duplicate_identity() -> None:
    key = ContextManagerKey("adaptive")
    registry = ContextManagerRegistry()
    descriptor = _descriptor(key)
    registry.register(key, _AlternateContextManager, descriptor=descriptor)

    with pytest.raises(DuplicateContextManagerError, match="adaptive"):
        registry.register(key, _AlternateContextManager, descriptor=descriptor)


def test_registry_rejects_unknown_identity() -> None:
    registry = build_context_manager_registry()

    with pytest.raises(UnknownContextManagerError, match="missing"):
        registry.create(ContextManagerKey("missing"))


def test_registry_rejects_incompatible_factory_result() -> None:
    key = ContextManagerKey("invalid")
    registry = ContextManagerRegistry()
    registry.register(
        key,
        lambda: object(),  # type: ignore[arg-type]
        descriptor=_descriptor(key),
    )

    with pytest.raises(InvalidContextManagerFactoryError, match="invalid"):
        registry.create(key)


def test_context_manager_key_is_name_only() -> None:
    assert ContextManagerKey.parse(" stdcm ") == ContextManagerKey("stdcm")
    assert str(ContextManagerKey(" adaptive ")) == "adaptive"

    with pytest.raises(ValueError, match="plain name"):
        ContextManagerKey.parse("stdcm:legacy")

    with pytest.raises(ValueError, match="must not be empty"):
        ContextManagerKey(" ")
