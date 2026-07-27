from __future__ import annotations

from modules.network.application.service import NetworkApplicationService
from shared.infra.errors import ConflictError


_VALID_SESSION_MODES = {"stateful", "stateless"}


def install_pinned_release_runtime_support() -> None:
    """Keep exact pinned Agent snapshots executable inside Network Draft.

    Draft Network executions still require a captured override object, while the
    Agent runtime itself gives ``release_id`` precedence and executes the exact
    immutable Agent snapshot. Freeze ``session_mode`` on the binding so runtime
    context preparation never needs to infer it from that compatibility override.
    """

    original = NetworkApplicationService._release_binding_payload

    def release_binding_payload(self, node_id, agent_id, release, source):
        payload = original(self, node_id, agent_id, release, source)
        session_mode = getattr(release.session_mode, "value", release.session_mode)
        if session_mode not in _VALID_SESSION_MODES:
            raise ConflictError(
                f"Agent snapshot has no valid Session Mode: {agent_id}"
            )
        payload["session_mode"] = str(session_mode)
        payload["snapshot_override"] = {
            "provider": release.provider,
            "model": release.model,
            "pinned_release_id": str(release.id),
        }
        return payload

    NetworkApplicationService._release_binding_payload = release_binding_payload
