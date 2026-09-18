from copy import deepcopy

import pytest
from uuid import uuid4

from modules.agent.application.execution_snapshot import (
    apply_agent_execution_snapshot,
    build_agent_execution_snapshot,
)
from modules.agent.domain.entities import Agent, AgentRelease
from modules.agent.domain.enums import Provider, ReleaseStatus, SessionMode


def _contract() -> dict:
    return {
        "customer_id": {
            "schema": {"type": "string"},
            "required": True,
            "scope": "run",
            "model": {"expose": False},
        }
    }


def test_legacy_agent_draft_snapshot_carries_external_context_contract() -> None:
    contract = _contract()
    agent = Agent(
        project_id=uuid4(),
        provider=Provider.custom,
        model="test-model",
        session_mode=SessionMode.stateless,
        settings={
            "runtime_config": {},
            "external_context_contract": deepcopy(contract),
        },
    )

    snapshot = build_agent_execution_snapshot(agent)

    assert snapshot["external_context_contract"] == contract
    assert snapshot["external_context_contract"] is not agent.settings["external_context_contract"]


def test_release_snapshot_and_apply_preserve_external_context_contract() -> None:
    project_id = uuid4()
    contract = _contract()
    release = AgentRelease(
        project_id=project_id,
        agent_id=uuid4(),
        version="1.0.0",
        status=ReleaseStatus.production,
        provider="custom",
        model="test-model",
        session_mode="stateless",
        runtime_config={},
        external_context_contract=deepcopy(contract),
    )
    target = Agent(
        project_id=project_id,
        provider=Provider.custom,
        model="old-model",
        session_mode=SessionMode.stateless,
        settings={
            "runtime_config": {},
            "external_context_contract": {},
        },
    )

    snapshot = build_agent_execution_snapshot(release)
    apply_agent_execution_snapshot(target, snapshot)

    assert snapshot["external_context_contract"] == contract
    assert target.settings["external_context_contract"] == contract
    assert target.settings["external_context_contract"] is not snapshot["external_context_contract"]


@pytest.mark.parametrize(
    "status",
    [ReleaseStatus.staging, ReleaseStatus.production],
)
def test_release_environment_keeps_frozen_external_context_when_draft_changes(status) -> None:
    project_id = uuid4()
    released_contract = {
        "name": {
            "schema": {"type": "string"},
            "required": True,
            "scope": "session",
            "model": {"expose": True},
            "description": "Frozen release description.",
        }
    }
    release = AgentRelease(
        project_id=project_id,
        agent_id=uuid4(),
        version="2.0.0",
        status=status,
        provider="custom",
        model="test-model",
        session_mode="stateful",
        runtime_config={},
        external_context_contract=deepcopy(released_contract),
    )
    target = Agent(
        project_id=project_id,
        provider=Provider.custom,
        model="draft-model",
        session_mode=SessionMode.stateful,
        settings={
            "runtime_config": {},
            "external_context_contract": {
                "name": {
                    "schema": {"type": "integer"},
                    "required": False,
                    "scope": "run",
                    "model": {"expose": False},
                    "description": "Mutated draft contract.",
                }
            },
        },
    )

    snapshot = build_agent_execution_snapshot(release)
    apply_agent_execution_snapshot(target, snapshot)

    assert target.settings["external_context_contract"] == released_contract
    assert target.settings["external_context_contract"]["name"]["scope"] == "session"
    assert target.settings["external_context_contract"]["name"]["model"]["expose"] is True
    assert (
        target.settings["external_context_contract"]["name"]["description"]
        == "Frozen release description."
    )


def test_release_external_context_snapshot_does_not_share_nested_references() -> None:
    contract = {
        "profile": {
            "schema": {
                "type": "object",
                "properties": {
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
            },
            "required": False,
            "scope": "session",
            "default": {"roles": ["viewer"]},
            "model": {"expose": True},
        }
    }
    release = AgentRelease(
        project_id=uuid4(),
        agent_id=uuid4(),
        version="1.0.0",
        status=ReleaseStatus.production,
        provider="custom",
        model="test-model",
        session_mode="stateful",
        runtime_config={},
        external_context_contract=contract,
    )

    snapshot = build_agent_execution_snapshot(release)
    contract["profile"]["default"]["roles"].append("mutated")

    assert snapshot["external_context_contract"]["profile"]["default"] == {
        "roles": ["viewer"]
    }
