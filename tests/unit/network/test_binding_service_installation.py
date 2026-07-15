import hashlib
import json

import modules.network  # noqa: F401 - installs explicit binding extensions
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
