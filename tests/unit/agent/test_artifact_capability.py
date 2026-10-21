from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.execution_snapshot import build_agent_execution_snapshot
from shared.contracts.artifact_capability import canonicalize_artifact_capability
from modules.agent.domain.execution_definition import hash_agent_execution_snapshot
from modules.agent.domain.release_snapshot import release_snapshot_hash
from shared.contracts.errors import ValidationError


def _external_context(*, scope="session", required=True, exposed=False, default=None, schema=None):
    field = {
        "schema": schema or {"type": "string"},
        "required": required,
        "scope": scope,
        "model": {"expose": exposed},
    }
    if default is not None:
        field["default"] = default
    return {"workspace": field}


def _enabled_capability(*, scope="session"):
    return {
        "enabled": True,
        "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": scope},
        "actions": ["read", "search"],
        "limits": {
            "max_search_results": 12,
            "max_read_chars": 4096,
            "max_total_read_chars": 20_000,
            "max_context_units": 6000,
        },
    }


def test_capability_is_off_by_default_and_normalizes_only_logical_policy():
    assert canonicalize_artifact_capability(None, None) is None
    result = canonicalize_artifact_capability(
        _enabled_capability(), _external_context()
    )
    assert result["enabled"] is True
    assert result["workspace_binding"] == {
        "field": "workspace",
        "namespace": "team-docs",
        "scope": "session",
    }
    assert result["limits"]["max_read_chars"] == 4096
    assert "workspace_id" not in repr(result)
    assert not any("id" in key for key in result)


@pytest.mark.parametrize(
    "capability",
    [
        {"enabled": True},
        {"enabled": True, "workspace_binding": {"field": "absent", "namespace": "team-docs", "scope": "session"}},
        {"enabled": True, "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": "run"}},
        {"enabled": True, "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": "session"}, "actions": ["read", "read"]},
        {"enabled": True, "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": "session"}, "actions": ["write"]},
        {"enabled": True, "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": "session"}, "actions": ["read"], "processing_profile": {"ref": "docs", "revision": 1}},
        {"enabled": True, "workspace_binding": {"field": "workspace", "namespace": "team-docs", "scope": "session"}, "limits": {"max_read_chars": 65_537}},
    ],
)
def test_invalid_artifact_policy_is_rejected(capability):
    with pytest.raises(ValidationError):
        canonicalize_artifact_capability(capability, _external_context())


@pytest.mark.parametrize(
    "external_context",
    [
        {},
        _external_context(required=False),
        _external_context(exposed=True),
        _external_context(default="workspace-1"),
        _external_context(schema={"type": "object"}),
    ],
)
def test_workspace_binding_must_be_an_explicit_hidden_external_context_string(external_context):
    with pytest.raises(ValidationError):
        canonicalize_artifact_capability(_enabled_capability(), external_context)


def test_artifact_policy_is_part_of_frozen_agent_execution_identity():
    first = _enabled_capability()
    changed = deepcopy(first)
    changed["limits"]["max_read_chars"] += 1
    external = _external_context()
    source = {
        "project_id": uuid4(),
        "agent_id": uuid4(),
        "provider": "custom",
        "model": "model-a",
        "session_mode": "stateful",
        "runtime_config": {"execution_strategy": "standard", "artifacts": first},
        "external_context_contract": external,
    }
    second = {**source, "runtime_config": {**source["runtime_config"], "artifacts": changed}}
    first_snapshot = build_agent_execution_snapshot(SimpleNamespace(**source))
    second_snapshot = build_agent_execution_snapshot(SimpleNamespace(**second))
    assert first_snapshot["runtime_config"]["artifacts"]["limits"]["max_read_chars"] == 4096
    assert hash_agent_execution_snapshot(first_snapshot) != hash_agent_execution_snapshot(second_snapshot)

    first_release = type("Release", (), {"runtime_config": first_snapshot["runtime_config"]})()
    second_release = type("Release", (), {"runtime_config": second_snapshot["runtime_config"]})()
    assert release_snapshot_hash(first_release) != release_snapshot_hash(second_release)


def test_existing_project_or_process_defaults_cannot_rewrite_a_release_snapshot():
    frozen = {"artifacts": canonicalize_artifact_capability(_enabled_capability(), _external_context())}
    source = {"project_id": uuid4(), "agent_id": uuid4(), "provider": "custom", "model": "model-a",
        "session_mode": "stateful", "runtime_config": frozen,
        "external_context_contract": _external_context()}
    release = build_agent_execution_snapshot(SimpleNamespace(**source))
    later_default = {"enabled": False}
    assert release["runtime_config"]["artifacts"]["enabled"] is True
    assert later_default != release["runtime_config"]["artifacts"]


def test_native_agent_draft_validates_artifact_policy_when_settings_are_saved():
    from modules.agent.application.use_cases.ai_agent_cases import _force_strict_json_settings
    from modules.agent.domain.entities import Agent

    agent = Agent(
        settings={
            "external_context_contract": _external_context(),
            "runtime_config": {"artifacts": _enabled_capability()},
        }
    )
    _force_strict_json_settings(agent, initialize_context_manager=True)
    assert agent.settings["runtime_config"]["artifacts"]["enabled"] is True

    invalid = Agent(settings={"runtime_config": {"artifacts": {"enabled": True}}})
    with pytest.raises(ValidationError):
        _force_strict_json_settings(invalid, initialize_context_manager=True)

