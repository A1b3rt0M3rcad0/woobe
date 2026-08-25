from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.agent.domain.release_compatibility import classify_release_change
from modules.agent.domain.release_versioning import calculate_next_release_version
from modules.agent.infra.database.models import AgentReleaseModel
from modules.network.domain.enums import NetworkEnvironment
from modules.network.domain.release_contracts import (
    agent_snapshot_hash,
    canonical_hash,
    classify_contract_change,
    output_contract_hash,
    output_contract_snapshot,
    runtime_settings_hash,
)
from modules.network.infra.database.models import (
    NetworkModel,
    NetworkProductionActivationModel,
    NetworkVersionModel,
)


def _next_staging_version(versions: list[str]) -> str:
    highest = 0
    for value in versions:
        if not value.startswith("staging-r"):
            continue
        try:
            highest = max(highest, int(value.removeprefix("staging-r")))
        except ValueError:
            continue
    return f"staging-r{highest + 1}"


async def _release_by_id(session, release_id: str | UUID | None):
    if not release_id:
        return None
    return await session.get(AgentReleaseModel, UUID(str(release_id)))


async def _equivalent_agent_snapshot(
    session,
    *,
    source: AgentReleaseModel,
    target_kind: str,
    active_only: bool,
    lock: bool,
):
    query = select(AgentReleaseModel).where(
        AgentReleaseModel.agent_id == source.agent_id,
        AgentReleaseModel.project_id == source.project_id,
        AgentReleaseModel.snapshot_kind == target_kind,
        AgentReleaseModel.id != source.id,
    )
    if active_only:
        query = query.where(AgentReleaseModel.status == target_kind)
    query = query.order_by(AgentReleaseModel.created_at.desc())
    if lock:
        query = query.with_for_update()
    for candidate in (await session.scalars(query)).all():
        if agent_snapshot_hash(candidate) == agent_snapshot_hash(source):
            return candidate
    return None


async def _candidate_manifest(session, definition, nodes: list[dict[str, Any]]):
    by_node = {str(item.get("node_id")): item for item in nodes}
    manifest: list[dict[str, Any]] = []
    entry_release = None
    for node in definition.nodes:
        item = by_node.get(str(node.id)) or {}
        release = await _release_by_id(session, item.get("selected_ref"))
        if release is None:
            continue
        record = {
            "node_id": str(node.id),
            "role": "entry" if node.id == definition.root_node_id else "specialist",
            "agent_id": str(node.agent_id),
            "release_id": str(release.id),
            "release_version": release.version,
            "snapshot_hash": agent_snapshot_hash(release),
            "output_contract_hash": output_contract_hash(release),
        }
        manifest.append(record)
        if node.id == definition.root_node_id:
            entry_release = release
    manifest.sort(key=lambda item: (item["role"] != "entry", item["node_id"]))
    return manifest, entry_release


async def _decorate_plan(self, session, definition, project_id, environment, *, lock=False):
    base = self._network_release_base_plan
    plan = await base(
        self,
        session,
        definition,
        project_id,
        environment,
        lock=lock,
    )
    removed_action_ids: set[str] = set()
    reused = 0
    for node in plan.get("nodes", []):
        action_id = node.get("action_id")
        action = node.get("action_required")
        if not action_id or not action:
            continue
        source = await _release_by_id(session, node.get("selected_ref"))
        if source is None:
            continue
        equivalent = None
        if action == "promote_draft_to_staging":
            equivalent = await _equivalent_agent_snapshot(
                session,
                source=source,
                target_kind="staging",
                active_only=True,
                lock=lock,
            )
        elif action == "publish_staging_to_release":
            equivalent = await _equivalent_agent_snapshot(
                session,
                source=source,
                target_kind="release",
                active_only=False,
                lock=lock,
            )
        if equivalent is None:
            node["snapshot_hash"] = agent_snapshot_hash(source)
            continue
        removed_action_ids.add(str(action_id))
        node["action_id"] = None
        node["action_required"] = None
        node["selected_ref"] = str(equivalent.id)
        node["selected_version"] = equivalent.version
        node["result_source"] = equivalent.snapshot_kind
        node["reuse_reason"] = (
            f"No execution-relevant changes since {equivalent.version}. "
            f"The existing Agent {equivalent.snapshot_kind.title()} snapshot will be reused."
        )
        node["snapshot_hash"] = agent_snapshot_hash(equivalent)
        reused += 1
    plan["actions"] = [
        action
        for action in plan.get("actions", [])
        if str(action.get("id")) not in removed_action_ids
    ]
    plan["reused_agent_count"] = reused

    network = await session.scalar(
        select(NetworkModel).where(NetworkModel.project_id == project_id)
    )
    if environment == NetworkEnvironment.STAGING:
        existing = []
        if network is not None:
            existing = list(
                (
                    await session.scalars(
                        select(NetworkVersionModel.version).where(
                            NetworkVersionModel.network_id == network.id,
                            NetworkVersionModel.kind == "staging",
                        )
                    )
                ).all()
            )
        plan["staging_preview"] = {
            "next_version": _next_staging_version(existing),
            "reused_agent_count": reused,
            "promotion_count": len(plan["actions"]),
        }
        return plan

    if environment == NetworkEnvironment.PRODUCTION and network is not None:
        candidate_manifest, entry_release = await _candidate_manifest(
            session, definition, plan.get("nodes", [])
        )
        candidate_contract = output_contract_snapshot(entry_release) if entry_release else None
        previous = (
            await session.get(NetworkVersionModel, network.production_version_id)
            if network.production_version_id
            else None
        )
        change_kind = classify_contract_change(
            previous.public_output_contract if previous else None,
            candidate_contract,
        )
        existing_versions = list(
            (
                await session.scalars(
                    select(NetworkVersionModel.version).where(
                        NetworkVersionModel.network_id == network.id,
                        NetworkVersionModel.kind == "release",
                    )
                )
            ).all()
        )
        previous_manifest = {
            str(item.get("node_id")): item
            for item in (previous.agent_release_manifest or [])
        } if previous else {}
        internal_warnings: list[str] = []
        for item in candidate_manifest:
            if item["role"] == "entry":
                continue
            before = previous_manifest.get(item["node_id"])
            if before and before.get("output_contract_hash") != item["output_contract_hash"]:
                internal_warnings.append(
                    f"Specialist Agent {item['agent_id']} changed its internal output contract."
                )
        plan["release_preview"] = {
            "change_kind": change_kind.value,
            "next_version": calculate_next_release_version(
                existing_versions, change_kind
            ),
            "entry_agent_id": str(entry_release.agent_id) if entry_release else None,
            "entry_agent_release_id": str(entry_release.id) if entry_release else None,
            "entry_agent_release_version": entry_release.version if entry_release else None,
            "public_output_contract": candidate_contract,
            "public_output_contract_hash": canonical_hash(candidate_contract),
            "agent_release_manifest": candidate_manifest,
            "internal_warnings": internal_warnings,
            "reused_agent_count": reused,
            "promotion_count": len(plan["actions"]),
        }
    return plan


async def _release_metadata(session, version: NetworkVersionModel, definition) -> dict[str, Any]:
    manifest: list[dict[str, Any]] = []
    entry_release = None
    for node in definition.nodes:
        binding = version.resolved_bindings.get(str(node.id)) or {}
        release = await _release_by_id(session, binding.get("release_id"))
        if release is None:
            continue
        item = {
            "node_id": str(node.id),
            "role": "entry" if node.id == definition.root_node_id else "specialist",
            "agent_id": str(node.agent_id),
            "release_id": str(release.id),
            "release_version": release.version,
            "snapshot_hash": agent_snapshot_hash(release),
            "output_contract_hash": output_contract_hash(release),
        }
        manifest.append(item)
        if node.id == definition.root_node_id:
            entry_release = release
    manifest.sort(key=lambda item: (item["role"] != "entry", item["node_id"]))
    public_contract = output_contract_snapshot(entry_release) if entry_release else None
    public_contract_hash = canonical_hash(public_contract)
    manifest_hash = canonical_hash(manifest)
    settings_hash = runtime_settings_hash(definition)
    fingerprint = canonical_hash(
        {
            "composition_hash": version.composition_hash,
            "public_output_contract_hash": public_contract_hash,
            "agent_release_manifest_hash": manifest_hash,
            "runtime_settings_hash": settings_hash,
        }
    )
    return {
        "entry_release": entry_release,
        "public_contract": public_contract,
        "public_contract_hash": public_contract_hash,
        "manifest": manifest,
        "manifest_hash": manifest_hash,
        "settings_hash": settings_hash,
        "fingerprint": fingerprint,
    }


async def _copy_agent_snapshot_semantic(
    self,
    session,
    source,
    *,
    target: str,
    promoted_by: UUID | None,
):
    if target == "staging":
        return await self._network_release_base_copy_agent_snapshot(
            session,
            source,
            target=target,
            promoted_by=promoted_by,
        )

    equivalent = await _equivalent_agent_snapshot(
        session,
        source=source,
        target_kind="release",
        active_only=False,
        lock=True,
    )
    if equivalent is not None:
        return equivalent

    active = list(
        (
            await session.scalars(
                select(AgentReleaseModel)
                .where(
                    AgentReleaseModel.agent_id == source.agent_id,
                    AgentReleaseModel.status == "production",
                    AgentReleaseModel.snapshot_kind == "release",
                )
                .with_for_update()
            )
        ).all()
    )
    previous = active[0] if active else None
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
    historical = [
        item.version for item in releases if item.snapshot_kind == "release"
    ]
    change_kind = classify_release_change(previous, source)
    version = calculate_next_release_version(historical, change_kind)
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
        status="production",
        snapshot_kind="release",
        release_notes=source.release_notes,
        promoted_by=promoted_by,
        promoted_at=datetime.now(timezone.utc),
    )
    session.add(clone)
    await session.flush()
    return clone


async def _promote_with_release_semantics(
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
    previous_production_id = None
    if environment == NetworkEnvironment.PRODUCTION:
        async with self._session_factory() as session:
            network = await session.get(NetworkModel, network_id)
            if network is not None:
                previous_production_id = network.production_version_id

    created = await self._network_release_base_promote(
        network_id=network_id,
        project_id=project_id,
        environment=environment,
        created_by=created_by,
        expected_revision=expected_revision,
        expected_network_version_id=expected_network_version_id,
        approved_action_ids=approved_action_ids,
    )

    async with self._session_factory() as session, session.begin():
        network = await session.get(NetworkModel, network_id, with_for_update=True)
        version = await session.get(NetworkVersionModel, created.id, with_for_update=True)
        if network is None or version is None:
            return created
        definition = self._definition(version.definition)
        metadata = await _release_metadata(session, version, definition)
        entry_release = metadata["entry_release"]
        entry_node = next(
            (node for node in definition.nodes if node.id == definition.root_node_id),
            None,
        )
        version.entry_agent_id = entry_node.agent_id if entry_node else None
        version.entry_agent_release_id = entry_release.id if entry_release else None
        version.entry_agent_release_version = entry_release.version if entry_release else None
        version.public_output_contract = deepcopy(metadata["public_contract"])
        version.public_output_contract_hash = metadata["public_contract_hash"]
        version.agent_release_manifest = deepcopy(metadata["manifest"])
        version.agent_release_manifest_hash = metadata["manifest_hash"]
        version.runtime_settings_hash = metadata["settings_hash"]
        version.release_fingerprint = metadata["fingerprint"]

        equivalent = await session.scalar(
            select(NetworkVersionModel)
            .where(
                NetworkVersionModel.network_id == network.id,
                NetworkVersionModel.kind == version.kind,
                NetworkVersionModel.release_fingerprint == metadata["fingerprint"],
                NetworkVersionModel.id != version.id,
            )
            .order_by(NetworkVersionModel.created_at.desc())
            .limit(1)
        )

        if environment == NetworkEnvironment.STAGING:
            version.source_draft_revision = network.draft_revision
            if equivalent is not None:
                network.staging_version_id = equivalent.id
                await session.delete(version)
                return equivalent
            staging_versions = list(
                (
                    await session.scalars(
                        select(NetworkVersionModel.version).where(
                            NetworkVersionModel.network_id == network.id,
                            NetworkVersionModel.kind == "staging",
                            NetworkVersionModel.id != version.id,
                        )
                    )
                ).all()
            )
            version.version = _next_staging_version(staging_versions)
            version.change_kind = "change"
            return version

        version.source_staging_version_id = expected_network_version_id
        previous = (
            await session.get(NetworkVersionModel, previous_production_id)
            if previous_production_id
            else None
        )
        change_kind = classify_contract_change(
            previous.public_output_contract if previous else None,
            metadata["public_contract"],
        )
        version.change_kind = change_kind.value
        if equivalent is not None:
            network.production_version_id = equivalent.id
            session.add(
                NetworkProductionActivationModel(
                    network_id=network.id,
                    project_id=project_id,
                    version_id=equivalent.id,
                    previous_version_id=previous_production_id,
                    activation_kind="reactivate",
                    change_description="Equivalent immutable Network Release reused during publish.",
                    created_by=created_by,
                )
            )
            await session.delete(version)
            return equivalent

        existing_versions = list(
            (
                await session.scalars(
                    select(NetworkVersionModel.version).where(
                        NetworkVersionModel.network_id == network.id,
                        NetworkVersionModel.kind == "release",
                        NetworkVersionModel.id != version.id,
                    )
                )
            ).all()
        )
        version.version = calculate_next_release_version(existing_versions, change_kind)
        version.activation_kind = "publish"
        version.change_description = version.change_description or "Published from the current Network Staging snapshot."
        session.add(
            NetworkProductionActivationModel(
                network_id=network.id,
                project_id=project_id,
                version_id=version.id,
                previous_version_id=previous_production_id,
                activation_kind="publish",
                change_description=version.change_description,
                created_by=created_by,
            )
        )
        return version


def install_network_release_lifecycle() -> None:
    from modules.network.application.service import NetworkApplicationService

    if hasattr(NetworkApplicationService, "_network_release_base_promote"):
        return
    NetworkApplicationService._network_release_base_plan = (  # type: ignore[attr-defined]
        NetworkApplicationService._build_promotion_plan
    )
    NetworkApplicationService._network_release_base_promote = (  # type: ignore[attr-defined]
        NetworkApplicationService.promote
    )
    NetworkApplicationService._network_release_base_copy_agent_snapshot = (  # type: ignore[attr-defined]
        NetworkApplicationService._copy_agent_snapshot
    )
    NetworkApplicationService._build_promotion_plan = _decorate_plan  # type: ignore[attr-defined]
    NetworkApplicationService._copy_agent_snapshot = _copy_agent_snapshot_semantic  # type: ignore[attr-defined]
    NetworkApplicationService.promote = _promote_with_release_semantics  # type: ignore[assignment]
