from __future__ import annotations

from modules.network.application.service import NetworkApplicationService


def install_pinned_release_runtime_support() -> None:
    """Keep Draft runtime compatible while it executes an exact pinned release.

    The runtime already gives ``release_id`` precedence over snapshot overrides,
    but Draft validation also requires a captured override. The minimal provider
    and model metadata below satisfies that invariant without duplicating the
    immutable Agent snapshot stored in the release row.
    """

    original = NetworkApplicationService._release_binding_payload

    def release_binding_payload(self, node_id, agent_id, release, source):
        payload = original(self, node_id, agent_id, release, source)
        payload["snapshot_override"] = {
            "provider": release.provider,
            "model": release.model,
            "pinned_release_id": str(release.id),
        }
        return payload

    NetworkApplicationService._release_binding_payload = release_binding_payload
