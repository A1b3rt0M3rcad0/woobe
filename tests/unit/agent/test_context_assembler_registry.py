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
    context_assembler_selection_from_runtime_config,
)
from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from shared.contracts.errors import ValidationError


class _AlternateContextAssembler:
    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        return SimpleNamespace(messages=request.messages, snapshot=SimpleNamespace())


def _descriptor(
    key: ContextAssemblerKey,
    *,
    display_name: str = "Alternate Context Manager",
) -> ContextAssemblerDescriptor:
    return ContextAssemblerDescriptor(
        key=key,
        strategy_key=key,
        display_name=display_name,
        description="Alternate context manager used by tests.",
        behavior="Assembles test context deterministically.",
        recommended_for=("Test workloads.",),
        capabilities=("Returns the provided messages.",),
        limitations=("Test implementation only.",),
        configuration="Test configuration",
    )


def test_default_registry_exposes_default_alias_and_explicit_standard_strategy() -> None:
    registry = build_context_assembler_registry()
    descriptors = registry.list_descriptors()

    assert DEFAULT_CONTEXT_ASSEMBLER_KEY == ContextAssemblerKey("default", "v1")
    assert STANDARD_CONTEXT_ASSEMBLER_KEY == ContextAssemblerKey("stdcm", "v1")
    assert [descriptor.key for descriptor in descriptors] == [
        DEFAULT_CONTEXT_ASSEMBLER_KEY,
        STANDARD_CONTEXT_ASSEMBLER_KEY,
        ContextAssemblerKey("stdcm", "v2"),
    ]

    system_default, explicit_standard, skills_standard = descriptors
    assert system_default.strategy_key == STANDARD_CONTEXT_ASSEMBLER_KEY
    assert system_default.display_name == "Standard Context Manager"
    assert system_default.is_default is True
    assert system_default.is_system_default_alias is True

    assert explicit_standard.strategy_key == STANDARD_CONTEXT_ASSEMBLER_KEY
    assert explicit_standard.display_name == "Standard Context Manager"
    assert explicit_standard.is_default is False
    assert explicit_standard.is_system_default_alias is False


def test_default_alias_and_explicit_strategy_resolve_same_standard_implementation() -> None:
    registry = build_context_assembler_registry()

    default_assembler = registry.create(DEFAULT_CONTEXT_ASSEMBLER_KEY)
    explicit_assembler = registry.create(STANDARD_CONTEXT_ASSEMBLER_KEY)

    assert isinstance(default_assembler, StandardContextAssembler)
    assert isinstance(explicit_assembler, StandardContextAssembler)
    assert isinstance(default_assembler, ContextAssembler)
    assert default_assembler is not explicit_assembler


def test_default_registry_exposes_backend_owned_product_metadata_for_both_selections() -> None:
    descriptors = list_context_assemblers()

    assert len(descriptors) == 3
    system_default, explicit_standard, skills_standard = descriptors

    expected_common = {
        "strategy_name": "stdcm",
        "strategy_version": "v1",
        "display_name": "Standard Context Manager",
        "description": (
            "Balanced deterministic context management for general-purpose Agent execution."
        ),
        "behavior": (
            "Builds each Model Invocation context deterministically from the Agent's available "
            "context sources, applying Context Policy v1 budgets, priorities, pressure handling, "
            "ordering, deduplication, and provenance capture."
        ),
        "recommended_for": [
            "General-purpose Agents that need predictable context behavior.",
            "Production workloads where replayability and stable snapshot behavior matter.",
        ],
        "capabilities": [
            "Preserves mandatory system instructions and the current user input.",
            "Balances session history, knowledge, tool, artifact, delegation, and runtime context within configured budgets.",
            "Applies pressure trimming, ordering, and deduplication before each Model Invocation.",
            "Records source contributions and provenance in the Context Snapshot.",
        ],
        "limitations": [
            "Does not perform autonomous context planning or iterative retrieval.",
            "Behavior is bounded by Context Policy v1 and the context sources available to the Agent.",
        ],
        "configuration": "Context Policy v1",
        "supports_skills": False,
    }

    assert system_default == {
        "name": "default",
        "version": "v1",
        **expected_common,
        "is_default": True,
        "is_system_default_alias": True,
    }
    assert explicit_standard == {
        "name": "stdcm",
        "version": "v1",
        **expected_common,
        "is_default": False,
        "is_system_default_alias": False,
    }


def test_build_context_assembler_resolves_through_fresh_registry() -> None:
    first = build_context_assembler(DEFAULT_CONTEXT_ASSEMBLER_KEY)
    second = build_context_assembler(DEFAULT_CONTEXT_ASSEMBLER_KEY)

    assert isinstance(first, StandardContextAssembler)
    assert isinstance(second, StandardContextAssembler)
    assert first is not second


def test_registry_accepts_structural_context_assembler_factory() -> None:
    key = ContextAssemblerKey("alternate", "v1")
    registry = ContextAssemblerRegistry()
    registry.register(key, _AlternateContextAssembler, descriptor=_descriptor(key))

    assembler = registry.create(key)

    assert isinstance(assembler, ContextAssembler)
    assert isinstance(assembler, _AlternateContextAssembler)


def test_registry_requires_explicit_product_metadata() -> None:
    key = ContextAssemblerKey("alternate", "v1")
    registry = ContextAssemblerRegistry()

    with pytest.raises(TypeError, match="descriptor"):
        registry.register(key, _AlternateContextAssembler)  # type: ignore[call-arg]


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
    key = ContextAssemblerKey("alternate", "v1")
    values: dict[str, object] = {
        "key": key,
        "strategy_key": key,
        "display_name": "Alternate Context Manager",
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


def test_registry_can_make_any_registered_strategy_the_system_default() -> None:
    key = ContextAssemblerKey("adaptive", "v2")
    registry = ContextAssemblerRegistry()
    registry.register(key, _AlternateContextAssembler, descriptor=_descriptor(key))

    alias_key = registry.register_default_alias(strategy_key=key)
    descriptor = registry.current_default()

    assert alias_key == ContextAssemblerKey("default", "v2")
    assert descriptor.key == alias_key
    assert descriptor.strategy_key == key
    assert descriptor.is_default is True
    assert descriptor.is_system_default_alias is True
    assert isinstance(registry.create(alias_key), _AlternateContextAssembler)


def test_registry_reserves_default_name_for_system_alias() -> None:
    key = ContextAssemblerKey("default", "v7")
    registry = ContextAssemblerRegistry()

    with pytest.raises(ValueError, match="reserved"):
        registry.register(key, _AlternateContextAssembler, descriptor=_descriptor(key))


def test_registry_rejects_default_alias_for_unregistered_strategy() -> None:
    registry = ContextAssemblerRegistry()

    with pytest.raises(
        InvalidDefaultContextManagerError,
        match="not registered: adaptive:v1",
    ):
        registry.register_default_alias(strategy_key=ContextAssemblerKey("adaptive", "v1"))


def test_registry_rejects_more_than_one_system_default() -> None:
    standard = ContextAssemblerKey("standard", "v1")
    adaptive = ContextAssemblerKey("adaptive", "v2")
    registry = ContextAssemblerRegistry()
    registry.register(standard, _AlternateContextAssembler, descriptor=_descriptor(standard))
    registry.register(adaptive, _AlternateContextAssembler, descriptor=_descriptor(adaptive))
    registry.register_default_alias(strategy_key=standard)

    with pytest.raises(InvalidDefaultContextManagerError, match="already registered"):
        registry.register_default_alias(strategy_key=adaptive)


def test_builder_rejects_unregistered_configured_default_strategy() -> None:
    with pytest.raises(
        InvalidDefaultContextManagerError,
        match="not registered: adaptive:v1",
    ):
        build_context_assembler_registry("adaptive:v1")


def test_builder_rejects_default_alias_as_configured_strategy() -> None:
    with pytest.raises(
        InvalidDefaultContextManagerError,
        match="concrete strategy",
    ):
        build_context_assembler_registry("default:v1")


def test_registry_dispatcher_resolves_frozen_strategy_identity() -> None:
    key = ContextAssemblerKey("alternate", "v1")
    registry = ContextAssemblerRegistry()
    registry.register(
        key,
        _AlternateContextAssembler,
        descriptor=_descriptor(key),
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
            context_assembler_name="default",
            context_assembler_version="v1",
            context_assembler_strategy_name="alternate",
            context_assembler_strategy_version="v1",
        ),
        policy=ContextPolicyV1(),
    )

    output = dispatcher.assemble(request)

    assert output.messages == ["hello"]


def test_registry_dispatcher_preserves_legacy_default_v1_behavior() -> None:
    registry = ContextAssemblerRegistry()
    registry.register(
        STANDARD_CONTEXT_ASSEMBLER_KEY,
        _AlternateContextAssembler,
        descriptor=_descriptor(STANDARD_CONTEXT_ASSEMBLER_KEY),
    )
    dispatcher = RegistryContextAssembler(registry)
    request = ContextAssemblyRequest(
        messages=["legacy"],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="test",
        model="test-model",
        runtime_context=SimpleNamespace(
            context_assembler_name="default",
            context_assembler_version="v1",
            context_assembler_strategy_name=None,
            context_assembler_strategy_version=None,
        ),
        policy=ContextPolicyV1(),
    )

    output = dispatcher.assemble(request)

    assert output.messages == ["legacy"]


def test_new_agent_canonicalization_freezes_system_default_and_strategy() -> None:
    assert canonicalize_context_assembler_runtime_config(
        {"other": True},
        use_current_default_if_missing=True,
    ) == {
        "other": True,
        "context_assembler": {
            "name": "default",
            "version": "v1",
            "strategy_name": "stdcm",
            "strategy_version": "v1",
        },
    }


def test_legacy_runtime_config_without_selection_keeps_original_default_behavior() -> None:
    assert canonicalize_context_assembler_runtime_config({"other": True}) == {
        "other": True,
        "context_assembler": {
            "name": "default",
            "version": "v1",
            "strategy_name": "stdcm",
            "strategy_version": "v1",
        },
    }


def test_explicit_strategy_selection_freezes_same_selection_and_strategy_identity() -> None:
    result = canonicalize_context_assembler_runtime_config(
        {
            "context_assembler": {
                "name": "stdcm",
                "version": "v1",
            }
        }
    )

    assert result["context_assembler"] == {
        "name": "stdcm",
        "version": "v1",
        "strategy_name": "stdcm",
        "strategy_version": "v1",
    }


def test_frozen_default_selection_keeps_its_resolved_strategy() -> None:
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

    assert selection.selection_key == ContextAssemblerKey("default", "v1")
    assert selection.strategy_key == ContextAssemblerKey("adaptive", "v1")


def test_default_selection_version_must_match_frozen_strategy_version() -> None:
    with pytest.raises(ValidationError, match="selection version must match"):
        canonicalize_context_assembler_runtime_config(
            {
                "context_assembler": {
                    "name": "default",
                    "version": "v2",
                    "strategy_name": "stdcm",
                    "strategy_version": "v1",
                }
            }
        )


def test_runtime_config_rejects_unregistered_strategy() -> None:
    with pytest.raises(
        ValidationError,
        match="Unsupported context assembler strategy: missing:v1",
    ):
        canonicalize_context_assembler_runtime_config(
            {"context_assembler": {"name": "missing", "version": "v1"}}
        )


def test_registry_rejects_duplicate_identity() -> None:
    key = ContextAssemblerKey("adaptive", "v1")
    registry = ContextAssemblerRegistry()
    descriptor = _descriptor(key)
    registry.register(key, _AlternateContextAssembler, descriptor=descriptor)

    with pytest.raises(DuplicateContextAssemblerError, match="adaptive:v1"):
        registry.register(key, _AlternateContextAssembler, descriptor=descriptor)


def test_registry_rejects_unknown_identity() -> None:
    registry = ContextAssemblerRegistry()

    with pytest.raises(UnknownContextAssemblerError, match="missing:v3"):
        registry.create(ContextAssemblerKey("missing", "v3"))


def test_registry_rejects_incompatible_factory_result() -> None:
    key = ContextAssemblerKey("invalid", "v1")
    registry = ContextAssemblerRegistry()
    registry.register(
        key,
        lambda: object(),  # type: ignore[arg-type]
        descriptor=_descriptor(key),
    )

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


def test_context_assembler_key_parses_environment_setting() -> None:
    assert ContextAssemblerKey.parse(" adaptive:v2 ") == ContextAssemblerKey(
        "adaptive",
        "v2",
    )

    with pytest.raises(ValueError, match="<name>:<version>"):
        ContextAssemblerKey.parse("adaptive")
