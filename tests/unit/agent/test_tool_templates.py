from __future__ import annotations

import pytest

from modules.agent.application.tool_templates import (
    ToolTemplateResolutionError,
    collect_project_environment_keys,
    resolve_tool_templates,
)


def test_collect_project_environment_keys_recursively() -> None:
    config = {
        "url": "{{project_env.API_URL}}/customers/{{external_context.customer_id}}",
        "headers": [
            {"key": "Authorization", "value": "Bearer {{project_env.API_KEY}}"},
        ],
        "body": {"tenant": "{{external_context.tenant_id}}"},
    }

    assert collect_project_environment_keys(config) == {"API_URL", "API_KEY"}


def test_resolve_tool_templates_preserves_exact_external_context_type() -> None:
    config = {
        "body": {
            "customer": "{{external_context.customer}}",
            "endpoint": "{{project_env.API_URL}}/v1",
        }
    }

    resolved = resolve_tool_templates(
        config,
        external_context={"customer": {"id": "cus_123"}},
        project_environment={"API_URL": "https://api.example.com"},
    )

    assert resolved == {
        "body": {
            "customer": {"id": "cus_123"},
            "endpoint": "https://api.example.com/v1",
        }
    }


def test_resolve_tool_templates_interpolates_scalar_values() -> None:
    resolved = resolve_tool_templates(
        "Bearer {{project_env.API_KEY}} / {{external_context.customer_id}}",
        external_context={"customer_id": "cus_123"},
        project_environment={"API_KEY": "secret"},
    )

    assert resolved == "Bearer secret / cus_123"


def test_missing_project_environment_key_fails_only_when_resolved() -> None:
    with pytest.raises(
        ToolTemplateResolutionError,
        match="Project Environment key 'API_KEY' is not configured",
    ):
        resolve_tool_templates(
            "{{project_env.API_KEY}}",
            external_context={},
            project_environment={},
        )


def test_missing_external_context_field_fails_when_resolved() -> None:
    with pytest.raises(
        ToolTemplateResolutionError,
        match="External Context field 'customer_id'",
    ):
        resolve_tool_templates(
            "{{external_context.customer_id}}",
            external_context={},
            project_environment={},
        )


def test_unknown_template_namespace_remains_literal() -> None:
    value = "{{future_namespace.some_key}}"

    assert resolve_tool_templates(
        value,
        external_context={},
        project_environment={},
    ) == value
