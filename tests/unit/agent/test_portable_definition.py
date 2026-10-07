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
