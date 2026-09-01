from __future__ import annotations

from dataclasses import replace

from modules.network.application.service import NetworkApplicationService
from modules.network.domain.entities import AgentBindingSelector
from modules.network.domain.enums import NetworkEnvironment
from modules.network.infra.database.models import NetworkVersionModel


def install_legacy_version_binding_compatibility() -> None:
    """Hydrate explicit selectors for immutable versions created before schema v2.

    Older Network Staging definitions did not store a selector on each node,
    but their ``resolved_bindings`` already pinned exact Agent release IDs. A
    Production promotion must use those historical bindings instead of treating
    the nodes as mutable Draft bindings.
    """

    original = NetworkApplicationService._promotion_source

    async def promotion_source(self, session, network, environment):
        definition, source_version_id = await original(
            self,
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
                source = "staging" if resolved.get("release_status") == "staging" else "release"
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

    NetworkApplicationService._promotion_source = promotion_source
