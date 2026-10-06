from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.model_connections import fallback_connection_settings
from modules.agent.application.portable_tool_bindings import (
    compile_imported_tool_inputs,
)
from modules.agent.application.tool_converter import agent_tools_to_openai_definitions
from shared.contracts.errors import ValidationError


def test_native_tool_compilation_remaps_only_declared_references_and_keeps_permissions():
    spec = {
        "type": "http",
        "permission": "deny",
        "risk": "high",
        "config": {
            "url": "{{ project_env.BASE_URL }}/customers",
            "method": "GET",
            "headers": [{"key": "Authorization", "value": "Bearer {{secret:service}}"}],
            "bindings": {
                "tenant": {"source": {"kind": "project_environment", "field": "TENANT"}}
            },
        },
    }
    result = compile_imported_tool_inputs(
        project_id=uuid4(),
        metadata={"name": "CRM"},
        spec=spec,
        environment={"BASE_URL": "DESTINATION_URL", "TENANT": "DESTINATION_TENANT"},
        secrets={"service": "destination-secret"},
    )
    assert result["config"]["url"] == "{{ project_env.DESTINATION_URL }}/customers"
    assert (
        result["config"]["headers"][0]["value"]
        == "Bearer {{secret:destination-secret}}"
    )
    assert (
        result["config"]["bindings"]["tenant"]["source"]["field"]
        == "DESTINATION_TENANT"
    )
    assert result["config"]["permission"] == {"mode": "deny", "risk_level": "high"}
    assert result["risk_level"] == "high"
    assert (
        agent_tools_to_openai_definitions([SimpleNamespace(id=uuid4(), **result)]) == []
    )
    with pytest.raises(ValidationError, match="undeclared"):
        compile_imported_tool_inputs(
            project_id=uuid4(),
            metadata={"name": "CRM"},
            spec=spec,
            environment={},
            secrets={},
        )


def test_fallback_endpoint_uses_its_full_model_snapshot_and_preserves_source():
    agent = SimpleNamespace(
        fallback_model="backup",
        settings={
            "base_url": "https://primary.test",
            "fallback_model_spec": {"metadata": {"base_url": "https://fallback.test"}},
        },
    )
    assert fallback_connection_settings(agent)["base_url"] == "https://fallback.test"
    assert agent.settings["base_url"] == "https://primary.test"
    agent.settings.pop("fallback_model_spec")
    assert fallback_connection_settings(agent)["base_url"] is None
