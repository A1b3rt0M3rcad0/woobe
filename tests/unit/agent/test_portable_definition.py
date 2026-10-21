import pytest
from uuid import uuid4

from modules.agent.contract_boundary import (
    inspect_portable_agent,
    inspect_portable_skill,
    inspect_portable_tool,
)
from shared.contracts.errors import ValidationError


def test_portable_agent_preserves_context_and_rejects_ignored_strategy_config():
    spec = {
        "execution": {
            "strategy": "standard",
            "config": {},
            "config_schema_version": "1",
        },
        "external_context": {
            "tenant": {
                "schema": {"type": "string"},
                "required": True,
                "scope": "session",
                "model": {"expose": False},
            }
        },
    }
    inspected = inspect_portable_agent(spec)
    assert inspected["external_context_contract"]["tenant"]["scope"] == "session"
    spec["execution"]["config"] = {"ignored_option": True}
    with pytest.raises(ValidationError, match="registered schema"):
        inspect_portable_agent(spec)


def test_agent_artifact_capability_is_portable_scoped_and_model_compatible():
    from modules.agent.domain.model_spec import (
        ModelCapability,
        ModelCapabilityNames,
        ModelInteractionSpec,
        ModelModalities,
        ModelOperations,
        ModelSpec,
        ModelTypes,
    )

    external_context = {
        "workspace": {
            "schema": {"type": "string"},
            "required": True,
            "scope": "session",
            "model": {"expose": False},
        }
    }
    capability = {
        "enabled": True,
        "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": "session"},
        "actions": ["read", "search"],
        "limits": {"max_search_results": 8, "max_read_chars": 2048},
        "processing_profile": None,
    }

    def model(supports_tools):
        return ModelSpec(
            provider="custom",
            model_id="portable-model",
            display_name="Portable Model",
            model_type=ModelTypes.LANGUAGE,
            operations=frozenset({ModelOperations.LANGUAGE_GENERATE}),
            input_modalities=frozenset({ModelModalities.TEXT}),
            output_modalities=frozenset({ModelModalities.TEXT}),
            interaction=ModelInteractionSpec(
                mode="conversation",
                supports_conversation=True,
                supports_history=True,
                supports_system_instruction=True,
                supports_context_injection=True,
            ),
            capabilities={
                ModelCapabilityNames.TOOL_CALLING: ModelCapability(
                    supported=supports_tools, source="provider"
                )
            },
        ).as_dict()

    spec = {"external_context": external_context, "artifacts": capability}
    inspected = inspect_portable_agent(spec, model_specs=[model(True)])
    assert inspected["artifact_capability"]["workspace_binding"] == {
        "field": "workspace",
        "namespace": "team-docs",
        "scope": "session",
    }
    assert "workspace_id" not in repr(inspected["artifact_capability"])
    with pytest.raises(ValidationError, match="incompatible"):
        inspect_portable_agent(spec, model_specs=[model(False)])

    # Legacy and non-tool Agents keep the default-off behavior.
    legacy = inspect_portable_agent({}, model_specs=[model(False)])
    assert legacy["artifact_capability"] is None


def test_artifact_only_agent_selects_no_knowledge_without_vector_model_compatibility():
    spec = {
        "knowledge_strategy": "none",
        "artifacts": {
            "enabled": True,
            "workspace_binding": {"field": "workspace", "namespace": "docs", "scope": "session"},
            "actions": ["read", "search"],
        },
        "external_context": {
            "workspace": {
                "schema": {"type": "string"}, "required": True,
                "scope": "session", "model": {"expose": False},
            }
        },
    }
    inspected = inspect_portable_agent(spec)
    assert inspected["knowledge_strategy"] == "none"
    assert inspected["knowledge_config"] == {}
    assert inspected["artifact_capability"]["enabled"] is True


def test_portable_agent_rejects_conflicting_knowledge_strategy_declarations():
    with pytest.raises(ValidationError, match="declarations conflict"):
        inspect_portable_agent({
            "knowledge_strategy": "none",
            "knowledge": {"strategy": "rag", "source": {"ref": "knowledge"}},
        })


@pytest.mark.parametrize(
    "external_context,capability",
    [
        ({}, {"enabled": True, "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": "run"}}),
        ({"workspace": {"schema": {"type": "string"}, "required": True, "scope": "session"}},
         {"enabled": True, "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": "run"}}),
        ({"workspace": {"schema": {"type": "object"}, "required": True}},
         {"enabled": True, "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": "run"}}),
        ({"workspace": {"schema": {"type": "string"}, "required": False}},
         {"enabled": True, "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": "run"}}),
        ({"workspace": {"schema": {"type": "string"}, "required": True, "default": "x"}},
         {"enabled": True, "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": "run"}}),
        ({"workspace": {"schema": {"type": "string"}, "required": True, "model": {"expose": True}}},
         {"enabled": True, "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": "run"}}),
    ],
)
def test_agent_artifact_capability_rejects_incoherent_external_context(external_context, capability):
    with pytest.raises(ValidationError):
        inspect_portable_agent({"external_context": external_context, "artifacts": capability})


def test_portable_tool_uses_native_http_group_compiler():
    result = inspect_portable_tool(
        project_id=uuid4(),
        metadata={"name": "Lookup"},
        spec={
            "type": "http",
            "risk": "high",
            "permission": "review",
            "config": {
                "mode": "group",
                "base_url": "https://example.test",
                "routes": [
                    {
                        "id": "fetch",
                        "name": "Fetch",
                        "description": "Fetch records",
                        "path": "/records",
                        "method": "GET",
                    }
                ],
            },
        },
    )
    assert result["create_input"]["risk_level"] == "high"
    assert result["binding_permission"] == "review"
    assert result["create_input"]["config"]["routes"][0]["id"] == "fetch"


def test_portable_skill_preserves_full_native_manifest_and_resource_contents():
    manifest = "---\nname: lookup\ndescription: Look up records\nallowed-tools: fetch\n---\nUse the reference.\n"
    result = inspect_portable_skill(
        version="1.0.0",
        skill_md=manifest,
        resources={"references/query.md": "Exact resource\n"},
        required_tools=["fetch"],
    )
    assert result["skill_md"] == manifest
    assert result["resources"]["references/query.md"] == "Exact resource\n"
    assert result["allowed_tools_hint"] == "fetch"
    assert result["required_tools"] == ["fetch"]


@pytest.mark.parametrize(
    "hint",
    [
        {"silently_discarded": True},
        {"interaction": {"supports_tools": True}},
        {"interaction": {"supports_conversation": "yes"}},
        {"limits": {"context_window": "4096"}},
        {"limits": {"context_window": 0}},
        {"capabilities": {"tool_calling": {"supported": "yes"}}},
        {"capabilities": {"tool_calling": {"unrecognized": True}}},
        {"spec_version": 2},
    ],
)
def test_portable_model_hint_cannot_drop_or_coerce_declared_fields(hint):
    from modules.agent.application.portable_definition import (
        inspect_proposed_provider_model,
    )

    with pytest.raises(ValidationError):
        inspect_proposed_provider_model(
            project_id=uuid4(),
            metadata={"name": "Model"},
            spec={
                "provider": "custom",
                "model": "custom-model",
                "model_spec_hint": hint,
            },
        )
