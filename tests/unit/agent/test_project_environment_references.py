from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.project_environment_references import (
    collect_tool_project_environment_keys,
    project_environment_tool_usage,
)


def test_collect_tool_project_environment_keys_unifies_templates_and_bindings() -> None:
    config = {
        "protocol": "http",
        "mode": "group",
        "base_url": "{{project_env.API_URL}}",
        "bindings": {
            "tenant": {
                "source": {
                    "kind": "project_environment",
                    "field": "TENANT_ID",
                }
            }
        },
        "routes": [
            {
                "id": "orders",
                "name": "Orders",
                "description": "List orders",
                "path": "/orders/{{external_context.customer_id}}",
                "headers": [
                    {
                        "key": "Authorization",
                        "value": "Bearer {{project_env.API_KEY}}",
                    }
                ],
            }
        ],
    }

    assert collect_tool_project_environment_keys(config) == {
        "API_URL",
        "TENANT_ID",
        "API_KEY",
    }


@pytest.mark.asyncio
async def test_list_project_environment_tool_references_returns_only_dependents() -> None:
    project_id = uuid4()
    matching = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        name="Billing API",
        config={"url": "{{project_env.API_URL}}/billing"},
    )
    unrelated = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        name="Search",
        config={"url": "https://search.example.com"},
    )
    repo = SimpleNamespace(
        list_by_project=lambda _project_id: None,
    )

    async def list_by_project(requested_project_id):
        assert requested_project_id == project_id
        return [matching, unrelated]

    repo.list_by_project = list_by_project

    usage = await project_environment_tool_usage(
        repo,
        project_id=project_id,
    )

    assert usage["API_URL"] == [
        {
            "id": str(matching.id),
            "name": "Billing API",
        }
    ]



@pytest.mark.asyncio
async def test_project_environment_tool_usage_aggregates_each_key_once() -> None:
    project_id = uuid4()
    first = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        name="Billing API",
        config={
            "url": "{{project_env.API_URL}}/billing",
            "headers": [
                {"key": "Authorization", "value": "Bearer {{project_env.API_KEY}}"}
            ],
        },
    )
    second = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        name="Orders API",
        config={"url": "{{project_env.API_URL}}/orders"},
    )

    calls = 0

    async def list_by_project(requested_project_id):
        nonlocal calls
        calls += 1
        assert requested_project_id == project_id
        return [first, second]

    usage = await project_environment_tool_usage(
        SimpleNamespace(list_by_project=list_by_project),
        project_id=project_id,
    )

    assert calls == 1
    assert [item["name"] for item in usage["API_URL"]] == [
        "Billing API",
        "Orders API",
    ]
    assert usage["API_KEY"] == [
        {"id": str(first.id), "name": "Billing API"},
    ]
