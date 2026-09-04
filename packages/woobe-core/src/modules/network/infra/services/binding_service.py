from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from modules.network.infra.services.service import NetworkApplicationService
from modules.network.domain.entities import AgentBindingSelector, NetworkDefinition
from modules.network.domain.enums import NetworkEnvironment, NetworkVersionKind
from modules.network.domain.graph import composition_hash
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from modules.network.infra.database.repositories import NetworkRepository
from shared.infra.errors import ConflictError, NotFoundError, ValidationError


class ExplicitBindingNetworkService(NetworkApplicationService):
    """Adds explicit, immutable Agent bindings to the Network lifecycle."""

    async def save_draft(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        expected_revision: int,
        name: str,
        description: str,
        definition: dict[str, Any],
    ) -> NetworkModel:
        parsed = self._definition(definition)
        async with self._session_factory() as session, session.begin():
            repository = NetworkRepository(session)
            network = await repository.get(network_id)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network not found")
            await self._validate_draft_bindings(session, parsed, project_id)
            saved = await repository.save_draft(
                network_id,
                expected_revision=expected_revision,
                name=name.strip() or network.name,
                description=description.strip(),
                definition=parsed.to_dict(),
            )
            if saved is None:
                raise ConflictError("Network Draft was changed by another request")
            return saved

    async def preview_promotion(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: NetworkEnvironment,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            network = await NetworkRepository(session).get(network_id)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network not found")
            definition, source_version_id = await self._promotion_source(
                session, network, environment
            )
            plan = await self._build_promotion_plan(
                session, definition, project_id, environment
            )
            return {
                "environment": environment.value,
                "network_revision": network.draft_revision,
                "network_version_id": str(source_version_id) if source_version_id else None,
                **plan,
            }

    async def promote(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: NetworkEnvironment,
        created_by: UUID | None,
        expected_revision: int | None = None,
        expected_network_version_id: UUID | None = None,
        approved_action_ids: list[str] | None = None,
    ) -> NetworkVersionModel:
        async with self._session_factory() as session, session.begin():
            network = await session.get(NetworkModel, network_id, with_for_update=True)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network not found")
            if (
                environment == NetworkEnvironment.STAGING
                and expected_revision is not None
                and expected_revision != network.draft_revision
            ):
                raise ConflictError(
                    "Network Draft changed after the promotion preview. Review the promotion again."
                )
            definition, source_version_id = await self._promotion_source(
                session, network, environment
            )
            if (
                environment == NetworkEnvironment.PRODUCTION
                and expected_network_version_id is not None
                and expected_network_version_id != source_version_id
            ):
                raise ConflictError(
                    "Network Staging changed after the promotion preview. Review the promotion again."
                )

            plan = await self._build_promotion_plan(
                session, definition, project_id, environment, lock=True
            )
            if not plan["ready"]:
                reasons = [
                    node["blocking_reason"]
                    for node in plan["nodes"]
                    if node["blocking_reason"]
                ]
                raise ConflictError("; ".join(reasons) or "Network promotion is not ready")

            required = {action["id"] for action in plan["actions"]}
            approved = required if approved_action_ids is None else set(approved_action_ids)
            if required - approved:
                raise ConflictError(
                    "Agent promotion approvals changed. Review the promotion again."
                )

            promoted: dict[str, Any] = {}
            for action in plan["actions"]:
                source = await self._get_release(
                    session,
                    UUID(action["source_release_id"]),
                    project_id,
                    UUID(action["agent_id"]),
                    lock=True,
                )
                if source is None:
                    raise ConflictError(
                        "Agent snapshot changed after the promotion preview. Review the promotion again."
                    )
                if action["action"] == "promote_draft_to_staging":
                    if source.status != "draft" or source.snapshot_kind != "draft":
                        raise ConflictError(
                            "Agent Draft changed after the promotion preview. Review the promotion again."
                        )
                    target = await self._copy_agent_snapshot(
                        session, source, target="staging", promoted_by=created_by
                    )
                else:
                    if source.snapshot_kind != "staging":
                        raise ConflictError(
                            "Agent Staging changed after the promotion preview. Review the promotion again."
                        )
                    target = await self._copy_agent_snapshot(
                        session, source, target="release", promoted_by=created_by
                    )
                promoted[action["id"]] = target

            nodes_by_id = {item["node_id"]: item for item in plan["nodes"]}
            final_nodes = []
            resolved_bindings: dict[str, dict[str, Any]] = {}
            for node in definition.nodes:
                item = nodes_by_id[str(node.id)]
                action_id = item.get("action_id")
                release = promoted.get(action_id)
                if release is None:
                    selected_ref = item.get("selected_ref")
                    release = await self._get_release(
                        session,
                        UUID(selected_ref) if selected_ref else None,
                        project_id,
                        node.agent_id,
                        lock=False,
                    )
                if release is None:
                    raise ConflictError(f"Agent binding is unavailable: {node.agent_id}")
                final_source = (
                    "release" if release.snapshot_kind == "release" else "staging"
                )
                if (
                    environment == NetworkEnvironment.PRODUCTION
                    and final_source != "release"
                ):
                    raise ConflictError(
                        "Network Production can only use immutable Agent Releases"
                    )
                final_nodes.append(
                    replace(
                        node,
                        binding=AgentBindingSelector(
                            source=final_source,
                            release_id=release.id,
                        ),
                    )
                )
                resolved_bindings[str(node.id)] = self._release_binding_payload(
                    node.id, node.agent_id, release, final_source
                )

            final_definition = replace(
                definition,
                nodes=tuple(final_nodes),
                schema_version=2,
            )
            kind = (
                NetworkVersionKind.STAGING
                if environment == NetworkEnvironment.STAGING
                else NetworkVersionKind.RELEASE
            )
            count = await session.scalar(
                select(func.count(NetworkVersionModel.id)).where(
                    NetworkVersionModel.network_id == network.id,
                    NetworkVersionModel.kind == kind.value,
                )
            )
            now = datetime.now(timezone.utc)
            version = NetworkVersionModel(
                network_id=network.id,
                project_id=project_id,
                kind=kind.value,
                version=f"v{int(count or 0) + 1}.{now:%Y%m%d.%H%M%S}",
                definition=final_definition.to_dict(),
                resolved_bindings=resolved_bindings,
                composition_hash=composition_hash(final_definition, resolved_bindings),
                created_by=created_by,
            )
            session.add(version)
            await session.flush()
            if environment == NetworkEnvironment.STAGING:
                network.staging_version_id = version.id
            else:
                network.production_version_id = version.id
            return version

    async def _promotion_source(
        self,
        session,
        network: NetworkModel,
        environment: NetworkEnvironment,
    ) -> tuple[NetworkDefinition, UUID | None]:
        if environment == NetworkEnvironment.STAGING:
            return self._definition(network.draft_definition), None
        if environment != NetworkEnvironment.PRODUCTION:
            raise ValidationError("Draft cannot be promoted as a runtime environment")
        if network.staging_version_id is None:
            raise ConflictError("Stage the Network before publishing Production")
        staging = await session.get(NetworkVersionModel, network.staging_version_id)
        if (
            staging is None
            or staging.network_id != network.id
            or staging.kind != "staging"
        ):
            raise ConflictError("Current Network Staging version was not found")
        return self._definition(staging.definition), staging.id

    async def _validate_draft_bindings(
        self,
        session,
        definition: NetworkDefinition,
        project_id: UUID,
    ) -> None:
        from modules.agent.infra.database.models import AgentModel

        for node in definition.nodes:
            agent = await session.scalar(
                select(AgentModel).where(
                    AgentModel.id == node.agent_id,
                    AgentModel.project_id == project_id,
                    AgentModel.status == "active",
                )
            )
            if agent is None:
                raise ConflictError(
                    f"Agent is unavailable for this Project: {node.agent_id}"
                )
            if node.binding.source == "draft":
                continue
            release = await self._get_release(
                session,
                node.binding.release_id,
                project_id,
                node.agent_id,
                lock=False,
            )
            if release is None or release.snapshot_kind != node.binding.source:
                raise ConflictError(
                    f"Agent {node.agent_id} does not own the selected "
                    f"{node.binding.source} snapshot"
                )

    async def _build_promotion_plan(
        self,
        session,
        definition: NetworkDefinition,
        project_id: UUID,
        environment: NetworkEnvironment,
        *,
        lock: bool = False,
    ) -> dict[str, Any]:
        from modules.agent.infra.database.models import AgentModel, AgentReleaseModel

        nodes: list[dict[str, Any]] = []
        actions_by_id: dict[str, dict[str, Any]] = {}
        for node in definition.nodes:
            agent = await session.scalar(
                select(AgentModel).where(
                    AgentModel.id == node.agent_id,
                    AgentModel.project_id == project_id,
                    AgentModel.status == "active",
                )
            )
            blocking_reason: str | None = None
            action: str | None = None
            selected_release = None
            if agent is None:
                blocking_reason = f"Agent is unavailable: {node.agent_id}"
            elif node.binding.source == "draft":
                if environment != NetworkEnvironment.STAGING:
                    blocking_reason = (
                        "Network Production cannot contain Agent Draft bindings"
                    )
                else:
                    query = select(AgentReleaseModel).where(
                        AgentReleaseModel.project_id == project_id,
                        AgentReleaseModel.agent_id == node.agent_id,
                        AgentReleaseModel.status == "draft",
                        AgentReleaseModel.snapshot_kind == "draft",
                    )
                    if lock:
                        query = query.with_for_update()
                    selected_release = await session.scalar(query)
                    if selected_release is None:
                        blocking_reason = (
                            "Save the Agent Draft before staging the Network"
                        )
                    else:
                        action = "promote_draft_to_staging"
            else:
                selected_release = await self._get_release(
                    session,
                    node.binding.release_id,
                    project_id,
                    node.agent_id,
                    lock=lock,
                )
                if (
                    selected_release is None
                    or selected_release.snapshot_kind != node.binding.source
                ):
                    blocking_reason = (
                        f"Selected Agent {node.binding.source} snapshot is unavailable"
                    )
                elif (
                    environment == NetworkEnvironment.PRODUCTION
                    and node.binding.source == "staging"
                ):
                    action = "publish_staging_to_release"
                elif (
                    environment == NetworkEnvironment.PRODUCTION
                    and node.binding.source != "release"
                ):
                    blocking_reason = (
                        "Network Production can only use Agent Releases"
                    )

            action_id = None
            if action and selected_release is not None:
                action_id = f"{action}:{selected_release.id}"
                actions_by_id.setdefault(
                    action_id,
                    {
                        "id": action_id,
                        "agent_id": str(node.agent_id),
                        "agent_name": getattr(agent, "name", str(node.agent_id)),
                        "action": action,
                        "source_release_id": str(selected_release.id),
                        "source_version": selected_release.version,
                    },
                )
            result_source = (
                "staging"
                if action == "promote_draft_to_staging"
                else "release"
                if action == "publish_staging_to_release"
                else node.binding.source
            )
            nodes.append(
                {
                    "node_id": str(node.id),
                    "agent_id": str(node.agent_id),
                    "agent_name": getattr(agent, "name", str(node.agent_id)),
                    "selected_source": node.binding.source,
                    "selected_ref": (
                        str(selected_release.id) if selected_release else None
                    ),
                    "selected_version": getattr(
                        selected_release, "version", None
                    ),
                    "result_source": result_source,
                    "action_required": action,
                    "action_id": action_id,
                    "blocking_reason": blocking_reason,
                }
            )
        return {
            "ready": all(node["blocking_reason"] is None for node in nodes),
            "nodes": nodes,
            "actions": list(actions_by_id.values()),
            "missing_agent_ids": [
                node["agent_id"] for node in nodes if node["blocking_reason"]
            ],
        }

    async def _get_release(
        self,
        session,
        release_id: UUID | None,
        project_id: UUID,
        agent_id: UUID,
        *,
        lock: bool,
    ):
        if release_id is None:
            return None
        from modules.agent.infra.database.models import AgentReleaseModel

        query = select(AgentReleaseModel).where(
            AgentReleaseModel.id == release_id,
            AgentReleaseModel.project_id == project_id,
            AgentReleaseModel.agent_id == agent_id,
        )
        if lock:
            query = query.with_for_update()
        return await session.scalar(query)

    async def _copy_agent_snapshot(
        self,
        session,
        source,
        *,
        target: str,
        promoted_by: UUID | None,
    ):
        from modules.agent.domain.release_versioning import (
            calculate_next_release_version,
        )
        from modules.agent.infra.database.models import AgentReleaseModel

        target_status = "staging" if target == "staging" else "production"
        active = list(
            (
                await session.scalars(
                    select(AgentReleaseModel)
                    .where(
                        AgentReleaseModel.agent_id == source.agent_id,
                        AgentReleaseModel.status == target_status,
                    )
                    .with_for_update()
                )
            ).all()
        )
        if target == "release":
            for current in active:
                if self._same_agent_snapshot(current, source):
                    return current
        for current in active:
            current.status = "archived"

        releases = list(
            (
                await session.scalars(
                    select(AgentReleaseModel).where(
                        AgentReleaseModel.agent_id == source.agent_id
                    )
                )
            ).all()
        )
        if target == "staging":
            number = 1 + sum(
                1 for item in releases if item.snapshot_kind == "staging"
            )
            used = {item.version for item in releases}
            while f"staging-r{number}" in used:
                number += 1
            version = f"staging-r{number}"
            snapshot_kind = "staging"
        else:
            historical = [
                item.version
                for item in releases
                if item.snapshot_kind == "release"
            ]
            version = calculate_next_release_version(historical, "change")
            snapshot_kind = "release"

        excluded = {
            "id",
            "created_at",
            "updated_at",
            "version",
            "status",
            "snapshot_kind",
            "promoted_by",
            "promoted_at",
            "release_notes",
        }
        values = {
            column.name: deepcopy(getattr(source, column.name))
            for column in AgentReleaseModel.__table__.columns
            if column.name not in excluded
        }
        clone = AgentReleaseModel(
            **values,
            version=version,
            status=target_status,
            snapshot_kind=snapshot_kind,
            release_notes=source.release_notes,
            promoted_by=promoted_by,
            promoted_at=datetime.now(timezone.utc),
        )
        session.add(clone)
        await session.flush()
        return clone

    @staticmethod
    def _same_agent_snapshot(left, right) -> bool:
        excluded = {
            "id",
            "created_at",
            "updated_at",
            "version",
            "status",
            "snapshot_kind",
            "promoted_by",
            "promoted_at",
            "release_notes",
        }
        return all(
            deepcopy(getattr(left, column.name))
            == deepcopy(getattr(right, column.name))
            for column in left.__table__.columns
            if column.name not in excluded
        )

    @staticmethod
    def _snapshot_hash(value: dict[str, Any]) -> str:
        encoded = json.dumps(
            value,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _release_binding_payload(
        self,
        node_id,
        agent_id,
        release,
        source: str,
    ) -> dict[str, Any]:
        return {
            "node_id": str(node_id),
            "agent_id": str(agent_id),
            "binding_source": source,
            "release_id": str(release.id),
            "release_version": release.version,
            "release_status": release.status,
            "snapshot_kind": release.snapshot_kind,
            "snapshot_hash": self._snapshot_hash(
                {
                    column.name: deepcopy(getattr(release, column.name))
                    for column in release.__table__.columns
                    if column.name
                    not in {
                        "id",
                        "created_at",
                        "updated_at",
                        "status",
                        "promoted_by",
                        "promoted_at",
                    }
                }
            ),
        }

    async def _resolve_draft_bindings(
        self,
        session,
        definition: NetworkDefinition,
        project_id: UUID,
    ) -> dict[str, dict[str, Any]]:
        from modules.agent.infra.database.models import AgentModel, AgentReleaseModel

        bindings: dict[str, dict[str, Any]] = {}
        for node in definition.nodes:
            agent = await session.scalar(
                select(AgentModel).where(
                    AgentModel.id == node.agent_id,
                    AgentModel.project_id == project_id,
                    AgentModel.status == "active",
                )
            )
            if agent is None:
                raise ConflictError(f"Agent is unavailable: {node.agent_id}")
            if node.binding.source != "draft":
                release = await self._get_release(
                    session,
                    node.binding.release_id,
                    project_id,
                    node.agent_id,
                    lock=False,
                )
                if (
                    release is None
                    or release.snapshot_kind != node.binding.source
                ):
                    raise ConflictError(
                        f"Pinned Agent snapshot is unavailable: {node.agent_id}"
                    )
                bindings[str(node.id)] = self._release_binding_payload(
                    node.id,
                    node.agent_id,
                    release,
                    node.binding.source,
                )
                continue

            draft_release = await session.scalar(
                select(AgentReleaseModel).where(
                    AgentReleaseModel.project_id == project_id,
                    AgentReleaseModel.agent_id == node.agent_id,
                    AgentReleaseModel.status == "draft",
                )
            )
            agent_settings = dict(agent.settings or {})
            runtime_config = deepcopy(
                getattr(draft_release, "runtime_config", None)
                or agent_settings.get("runtime_config")
            )
            snapshot = {
                "system_prompt": (
                    draft_release.system_prompt
                    if draft_release and draft_release.system_prompt is not None
                    else agent.system_prompt
                ),
                "response_format": (
                    draft_release.response_format
                    if draft_release and draft_release.response_format is not None
                    else agent_settings.get("response_format")
                ),
                "provider": (
                    draft_release.provider
                    if draft_release and draft_release.provider is not None
                    else agent.provider
                ),
                "model": (
                    draft_release.model
                    if draft_release and draft_release.model is not None
                    else agent.model
                ),
                "provider_credential_id": self._uuid_text(
                    draft_release.provider_credential_id
                    if draft_release
                    and draft_release.provider_credential_id is not None
                    else agent.provider_credential_id
                ),
                "provider_model_id": self._uuid_text(
                    getattr(draft_release, "provider_model_id", None)
                    or getattr(agent, "provider_model_id", None)
                ),
                "fallback_provider": (
                    draft_release.fallback_provider
                    if draft_release and draft_release.fallback_provider is not None
                    else agent.fallback_provider
                ),
                "fallback_model": (
                    draft_release.fallback_model
                    if draft_release and draft_release.fallback_model is not None
                    else agent.fallback_model
                ),
                "fallback_credential_id": self._uuid_text(
                    draft_release.fallback_credential_id
                    if draft_release
                    and draft_release.fallback_credential_id is not None
                    else agent.fallback_credential_id
                ),
                "fallback_provider_model_id": self._uuid_text(
                    getattr(draft_release, "fallback_provider_model_id", None)
                    or getattr(agent, "fallback_provider_model_id", None)
                ),
                "temperature": (
                    draft_release.temperature
                    if draft_release and draft_release.temperature is not None
                    else agent.temperature
                ),
                "max_output_tokens": (
                    draft_release.max_output_tokens
                    if draft_release and draft_release.max_output_tokens is not None
                    else agent.max_output_tokens
                ),
                "session_mode": (
                    draft_release.session_mode
                    if draft_release and draft_release.session_mode is not None
                    else agent.session_mode
                ),
                "runtime_config": runtime_config,
            }
            bindings[str(node.id)] = {
                "node_id": str(node.id),
                "agent_id": str(node.agent_id),
                "binding_source": "draft",
                "draft_release_id": self._uuid_text(
                    draft_release.id if draft_release else None
                ),
                "snapshot_override": snapshot,
                "snapshot_hash": self._snapshot_hash(snapshot),
            }
        return bindings


def install_explicit_binding_service() -> None:
    """Install explicit bindings without changing existing route imports."""

    names = (
        "save_draft",
        "preview_promotion",
        "promote",
        "_promotion_source",
        "_validate_draft_bindings",
        "_build_promotion_plan",
        "_get_release",
        "_copy_agent_snapshot",
        "_same_agent_snapshot",
        "_snapshot_hash",
        "_release_binding_payload",
        "_resolve_draft_bindings",
    )
    for name in names:
        setattr(
            NetworkApplicationService,
            name,
            getattr(ExplicitBindingNetworkService, name),
        )

