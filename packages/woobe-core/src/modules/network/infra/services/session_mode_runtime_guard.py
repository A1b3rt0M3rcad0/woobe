from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.agent.infra.database.models import AgentReleaseModel
from modules.network.domain.enums import NetworkEnvironment
from shared.infra.errors import ConflictError


_VALID_SESSION_MODES = {"stateful", "stateless"}


def _session_mode_value(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    return str(raw) if raw in _VALID_SESSION_MODES else None


def install_runtime_session_mode_guards() -> None:
    """Keep Agent Session Mode frozen after legacy Network service installers run.

    Network still composes some lifecycle behavior through import-time installers.
    The explicit-binding installer replaces the session-mode-aware methods inherited
    by the public service, so install this guard last and preserve the runtime
    invariant at the Acceptance/promotion boundaries rather than adding SQL reads
    to the hot execution path.
    """

    from modules.network.infra.services.service import NetworkApplicationService

    resolve_draft_bindings = NetworkApplicationService._resolve_draft_bindings
    promote_network = NetworkApplicationService.promote
    rollback_production = NetworkApplicationService.rollback_production

    async def frozen_draft_bindings(
        self,
        session,
        definition,
        project_id: UUID,
    ) -> dict[str, dict[str, Any]]:
        bindings = await resolve_draft_bindings(
            self,
            session,
            definition,
            project_id,
        )

        for node in definition.nodes:
            binding = bindings.get(str(node.id))
            if not isinstance(binding, dict):
                raise ConflictError(
                    f"Invalid Agent binding for Network node: {node.id}"
                )

            mode = _session_mode_value(binding.get("session_mode"))
            snapshot = binding.get("snapshot_override")
            if mode is None and isinstance(snapshot, dict):
                mode = _session_mode_value(snapshot.get("session_mode"))

            if mode is None and binding.get("release_id"):
                try:
                    release_id = UUID(str(binding["release_id"]))
                except (TypeError, ValueError) as exc:
                    raise ConflictError(
                        f"Network node has no valid immutable Agent binding: {node.id}"
                    ) from exc
                release = await session.get(AgentReleaseModel, release_id)
                if (
                    release is None
                    or release.project_id != project_id
                    or release.agent_id != node.agent_id
                ):
                    raise ConflictError(
                        f"Agent snapshot pinned by Network node was not found: {node.id}"
                    )
                mode = _session_mode_value(release.session_mode)

            if mode is None:
                raise ConflictError(
                    f"Agent snapshot has no valid Session Mode: {node.id}"
                )

            binding["session_mode"] = mode

        return bindings

    async def promote_with_frozen_session_modes(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: NetworkEnvironment,
        created_by: UUID | None,
        expected_revision: int | None = None,
        expected_network_version_id: UUID | None = None,
        approved_action_ids: list[str] | None = None,
    ):
        version = await promote_network(
            self,
            network_id=network_id,
            project_id=project_id,
            environment=environment,
            created_by=created_by,
            expected_revision=expected_revision,
            expected_network_version_id=expected_network_version_id,
            approved_action_ids=approved_action_ids,
        )
        return await self._freeze_version_session_modes(
            version_id=version.id,
            project_id=project_id,
        )

    async def rollback_with_frozen_session_modes(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        target_version_id: UUID,
        created_by: UUID | None,
    ):
        version = await rollback_production(
            self,
            network_id=network_id,
            project_id=project_id,
            target_version_id=target_version_id,
            created_by=created_by,
        )
        return await self._freeze_version_session_modes(
            version_id=version.id,
            project_id=project_id,
        )

    NetworkApplicationService._resolve_draft_bindings = frozen_draft_bindings
    NetworkApplicationService.promote = promote_with_frozen_session_modes
    NetworkApplicationService.rollback_production = rollback_with_frozen_session_modes

