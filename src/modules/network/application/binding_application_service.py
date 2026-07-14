from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from uuid import UUID

from modules.network.application.binding_service import ExplicitBindingNetworkService
from modules.network.domain.entities import AgentBindingSelector
from modules.network.domain.enums import NetworkEnvironment
from modules.network.infra.database.models import NetworkVersionModel


class BindingAwareNetworkApplicationService(ExplicitBindingNetworkService):
    """Production Network application service with explicit Agent bindings."""

    async def _promotion_source(self, session, network, environment):
        definition, source_version_id = await super()._promotion_source(
            session,
            network,
            environment,
        )
        if (
            environment != NetworkEnvironment.PRODUCTION
            or source_version_id is None
        ):
            return definition, source_version_id

        version = await session.get(NetworkVersionModel, source_version_id)
        resolved_bindings = dict(version.resolved_bindings or {}) if version else {}
        nodes = []
        changed = False
        for node in definition.nodes:
            if node.binding.source != "draft":
                nodes.append(node)
                continue
            resolved = resolved_bindings.get(str(node.id)) or {}
            release_id = resolved.get("release_id")
            if not release_id:
                nodes.append(node)
                continue
            source = resolved.get("binding_source") or resolved.get("snapshot_kind")
            if source not in {"staging", "release"}:
                source = (
                    "staging"
                    if resolved.get("release_status") == "staging"
                    else "release"
                )
            nodes.append(
                replace(
                    node,
                    binding=AgentBindingSelector.from_dict(
                        {"source": source, "release_id": release_id}
                    ),
                )
            )
            changed = True
        if changed:
            definition = replace(definition, nodes=tuple(nodes), schema_version=2)
        return definition, source_version_id

    async def _build_promotion_plan(
        self,
        session,
        definition,
        project_id: UUID,
        environment,
        *,
        lock: bool = False,
    ):
        plan = await super()._build_promotion_plan(
            session,
            definition,
            project_id,
            environment,
            lock=lock,
        )
        action_ids: dict[str, str] = {}
        for action in plan.get("actions", []):
            old_id = action["id"]
            release = await self._get_release(
                session,
                UUID(action["source_release_id"]),
                project_id,
                UUID(action["agent_id"]),
                lock=False,
            )
            if release is None:
                continue
            excluded = {
                "id",
                "created_at",
                "updated_at",
                "status",
                "promoted_by",
                "promoted_at",
            }
            snapshot_hash = self._snapshot_hash(
                {
                    column.name: deepcopy(getattr(release, column.name))
                    for column in release.__table__.columns
                    if column.name not in excluded
                }
            )
            new_id = f"{old_id}:{snapshot_hash}"
            action["id"] = new_id
            action["source_snapshot_hash"] = snapshot_hash
            action_ids[old_id] = new_id

        for node in plan.get("nodes", []):
            old_id = node.get("action_id")
            if old_id in action_ids:
                node["action_id"] = action_ids[old_id]
        return plan

    def _release_binding_payload(self, node_id, agent_id, release, source):
        payload = super()._release_binding_payload(
            node_id,
            agent_id,
            release,
            source,
        )
        payload["snapshot_override"] = {
            "provider": release.provider,
            "model": release.model,
            "pinned_release_id": str(release.id),
        }
        return payload
