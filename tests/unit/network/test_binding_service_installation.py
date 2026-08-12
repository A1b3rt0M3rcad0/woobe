import hashlib
import json
from uuid import uuid4

import modules.network  # noqa: F401 - installs explicit binding extensions
from modules.agent.infra.database.models import AgentReleaseModel
from modules.network.application.service import NetworkApplicationService


def test_explicit_binding_helpers_remain_static_after_installation() -> None:
    assert isinstance(
        NetworkApplicationService.__dict__["_snapshot_hash"],
        staticmethod,
    )
    assert isinstance(
        NetworkApplicationService.__dict__["_same_agent_snapshot"],
        staticmethod,
    )

    service = object.__new__(NetworkApplicationService)
    payload = {"agent_id": "agent-1", "version": 3}
    expected = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

    assert service._snapshot_hash(payload) == expected


def test_pinned_release_binding_freezes_agent_session_mode() -> None:
    service = object.__new__(NetworkApplicationService)
    project_id = uuid4()
    agent_id = uuid4()
    node_id = uuid4()
    release_id = uuid4()
    release = AgentReleaseModel(
        id=release_id,
        project_id=project_id,
        agent_id=agent_id,
        version="staging-r3",
        status="staging",
        snapshot_kind="staging",
        session_mode="stateful",
        provider="custom",
        model="deepseek-v4-flash",
    )

    payload = service._release_binding_payload(
        node_id,
        agent_id,
        release,
        "staging",
    )

    assert payload["release_id"] == str(release_id)
    assert payload["session_mode"] == "stateful"
    assert payload["snapshot_override"] == {
        "provider": "custom",
        "model": "deepseek-v4-flash",
        "pinned_release_id": str(release_id),
    }
