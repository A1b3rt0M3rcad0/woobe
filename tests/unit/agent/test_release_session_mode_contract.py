from dataclasses import replace
from uuid import uuid4

from modules.agent.application.use_cases.auto_compatible_release_lifecycle import (
    _execution_snapshot_equal,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.release_compatibility import classify_release_change
from modules.agent.domain.release_versioning import ReleaseChangeKind
from modules.agent.presentation.controllers.list_releases_controller import (
    _release_list_payload,
)


def make_release(*, session_mode: str, version: str = "v1.0.0") -> AgentRelease:
    release = AgentRelease(
        project_id=uuid4(),
        agent_id=uuid4(),
        version=version,
        status=ReleaseStatus.released,
        provider="openai",
        model="gpt-4o-mini",
        system_prompt="prompt",
        session_mode=session_mode,
    )
    release.snapshot_kind = "release"
    return release


def clone_release(release: AgentRelease, *, session_mode: str) -> AgentRelease:
    clone = replace(release, id=uuid4(), session_mode=session_mode)
    clone.snapshot_kind = getattr(release, "snapshot_kind", None)
    return clone


def test_release_list_payload_preserves_snapshot_kind_and_session_mode() -> None:
    release = make_release(session_mode="stateless")

    payload = _release_list_payload(release)

    assert payload["project_id"] == release.project_id
    assert payload["agent_id"] == release.agent_id
    assert payload["snapshot_kind"] == "release"
    assert payload["session_mode"] == "stateless"


def test_stateful_and_stateless_snapshots_are_not_equivalent() -> None:
    stateful = make_release(session_mode="stateful")
    stateless = clone_release(stateful, session_mode="stateless")

    assert not _execution_snapshot_equal(stateful, stateless)


def test_stateful_to_stateless_is_compatibility_change() -> None:
    previous = make_release(session_mode="stateful")
    candidate = clone_release(previous, session_mode="stateless")

    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_stateless_to_stateful_is_compatibility_change() -> None:
    previous = make_release(session_mode="stateless")
    candidate = clone_release(previous, session_mode="stateful")

    assert classify_release_change(previous, candidate) == ReleaseChangeKind.COMPATIBILITY


def test_release_list_payload_preserves_external_context_contract() -> None:
    release = make_release(session_mode="stateless")
    release.external_context_contract = {
        "name": {
            "schema": {"type": "string"},
            "required": True,
            "scope": "run",
            "model": {"expose": True},
            "description": "Preferred name of the current user",
        }
    }

    payload = _release_list_payload(release)

    assert payload["external_context_contract"] == release.external_context_contract
