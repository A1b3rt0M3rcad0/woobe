"""Capture one Network selector and its exact Agent bindings in one SQL snapshot."""

from copy import deepcopy
from uuid import UUID

from sqlalchemy import select, text

from modules.network.domain.graph import composition_hash
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from shared.contracts.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal
from shared.security.tenancy import TenantAuthorizer


class PortableNetworkExportReader:
    def __init__(self, session_factory, service, agent_reader):
        self._sessions, self._service, self._agents = (
            session_factory,
            service,
            agent_reader,
        )

    async def capture(
        self, *, project_id, principal, network_id, source=None, snapshot_id=None
    ):
        if (source is None) == (snapshot_id is None):
            raise ValidationError("Export requires source or snapshot identity")
        async with self._sessions.begin() as session:
            if session.bind.dialect.name == "postgresql":
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                )
            authorizer = TenantAuthorizer(session)
            paths = {"project_id": str(project_id), "network_id": str(network_id)}
            if isinstance(principal, ControlPlanePrincipal):
                await authorizer.require_active_control(principal)
                await authorizer.authorize_control_key(
                    api_key_id=principal.api_key_id,
                    workspace_id=principal.workspace_id,
                    workspace_permissions=principal.permissions,
                    required_permission="network:read",
                    path_params=paths,
                    query_params={},
                    body={},
                )
            elif isinstance(principal, AuthenticatedPrincipal):
                await authorizer.require_active_human(principal)
                workspace_id = await authorizer._project_workspace_id(project_id)
                await authorizer.require_human_permission(
                    user_id=principal.user_id,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    permission="network:read",
                    path_context=paths,
                )
            else:
                raise AuthorizationError("Administrative authentication is required")
            network = await session.get(NetworkModel, network_id)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network is unavailable")
            version = None
            if snapshot_id is not None:
                version = await session.get(NetworkVersionModel, snapshot_id)
            elif source in {"staging", "production"}:
                identifier = (
                    network.staging_version_id
                    if source == "staging"
                    else network.production_version_id
                )
                version = (
                    await session.get(NetworkVersionModel, identifier)
                    if identifier
                    else None
                )
            elif source == "release":
                version = await session.scalar(
                    select(NetworkVersionModel)
                    .where(
                        NetworkVersionModel.network_id == network_id,
                        NetworkVersionModel.project_id == project_id,
                        NetworkVersionModel.kind == "release",
                    )
                    .order_by(
                        NetworkVersionModel.created_at.desc(),
                        NetworkVersionModel.id.desc(),
                    )
                    .limit(1)
                )
            elif source != "draft":
                raise ValidationError("Invalid Network export source")
            if version is None and source != "draft":
                raise NotFoundError("Network snapshot is unavailable")
            if version is not None:
                if (
                    version.network_id != network_id
                    or version.project_id != project_id
                    or version.kind not in {"staging", "release"}
                ):
                    raise NotFoundError("Network snapshot is unavailable")
                definition = self._service._definition(deepcopy(version.definition))
                bindings = deepcopy(version.resolved_bindings)
                if composition_hash(definition, bindings) != version.composition_hash:
                    raise ConflictError("Network snapshot integrity check failed")
            else:
                definition = self._service._definition(
                    deepcopy(network.draft_definition)
                )
                bindings = await self._service._resolve_draft_bindings(
                    session, definition, project_id
                )
            agents, selections = [], {}
            nodes = []
            keys = {
                node.id: node.portable_key or f"node-{index + 1}"
                for index, node in enumerate(definition.nodes)
            }
            for node in definition.nodes:
                binding = bindings.get(str(node.id)) or {}
                release_id = binding.get("release_id") or binding.get(
                    "draft_release_id"
                )
                live_draft = (
                    release_id is None
                    and version is None
                    and node.binding.source == "draft"
                )
                if release_id is None and not live_draft:
                    raise ConflictError(
                        "Network binding has no complete Agent snapshot"
                    )
                identity = (
                    node.agent_id,
                    UUID(str(release_id)) if release_id else None,
                )
                if identity not in selections:
                    reference = f"agent-{len(agents) + 1}"
                    captured = await self._agents.capture_in_session(
                        session,
                        project_id=project_id,
                        principal=principal,
                        agent_id=node.agent_id,
                        source="draft" if live_draft else None,
                        snapshot_id=identity[1],
                        expected_snapshot=None
                        if live_draft
                        else binding.get("snapshot_override"),
                    )
                    agents.append({"key": reference, **captured})
                    selections[identity] = reference
                nodes.append(
                    {
                        "key": keys[node.id],
                        "agent_ref": selections[identity],
                        "label": node.label,
                        "capability_description": node.capability_description,
                        "position": deepcopy(node.position),
                        "binding": {"source": node.binding.source},
                    }
                )
            return {
                "source": {
                    "network_id": str(network.id),
                    "snapshot_id": str(version.id) if version else None,
                    "revision": network.draft_revision if version is None else None,
                    "version": version.version if version else None,
                    "kind": version.kind if version else "draft",
                },
                "name": (definition.author_metadata or {}).get("name", network.name),
                "description": (definition.author_metadata or {}).get(
                    "description", network.description or ""
                ),
                "spec": {
                    "root": keys[definition.root_node_id],
                    "nodes": nodes,
                    "edges": [
                        {
                            "from": keys[edge.source_node_id],
                            "to": keys[edge.target_node_id],
                        }
                        for edge in definition.edges
                    ],
                    "settings": definition.to_dict()["settings"],
                },
                "agents": agents,
            }
