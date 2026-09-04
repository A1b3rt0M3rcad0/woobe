# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.agent.domain.release_versioning import calculate_next_release_version
from modules.network.infra.services.release_lifecycle import _next_staging_version, _release_metadata
from modules.network.domain.entities import AgentBindingSelector
from modules.network.domain.enums import NetworkEnvironment, NetworkVersionKind
from modules.network.domain.graph import composition_hash
from modules.network.domain.release_contracts import classify_contract_change
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from modules.network.infra.database.schema_extensions import NetworkProductionActivationModel
from shared.infra.errors import ConflictError, NotFoundError


async def _promote_atomic(
    self: Any,
    *,
    network_id: UUID,
    project_id: UUID,
    environment: NetworkEnvironment,
    created_by: UUID | None,
    expected_revision: int | None = None,
    expected_network_version_id: UUID | None = None,
    approved_action_ids: list[str] | None = None,
):
    async with self._session_factory() as session, session.begin():
        network = await session.get(NetworkModel, network_id, with_for_update=True)
        if network is None or network.project_id != project_id:
            raise NotFoundError("Network not found")
        if environment == NetworkEnvironment.STAGING and expected_revision is not None and expected_revision != network.draft_revision:
            raise ConflictError("Network Draft changed after the promotion preview. Review the promotion again.")

        definition, source_version_id = await self._promotion_source(session, network, environment)
        if environment == NetworkEnvironment.PRODUCTION and expected_network_version_id is not None and expected_network_version_id != source_version_id:
            raise ConflictError("Network Staging changed after the promotion preview. Review the promotion again.")

        plan = await self._build_promotion_plan(session, definition, project_id, environment, lock=True)
        if not plan["ready"]:
            reasons = [node["blocking_reason"] for node in plan["nodes"] if node["blocking_reason"]]
            raise ConflictError("; ".join(reasons) or "Network promotion is not ready")

        required = {action["id"] for action in plan["actions"]}
        approved = required if approved_action_ids is None else set(approved_action_ids)
        if required - approved:
            raise ConflictError("Agent promotion approvals changed. Review the promotion again.")

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
                raise ConflictError("Agent snapshot changed after the promotion preview. Review the promotion again.")
            if action["action"] == "promote_draft_to_staging":
                if source.status != "draft" or source.snapshot_kind != "draft":
                    raise ConflictError("Agent Draft changed after the promotion preview. Review the promotion again.")
                target = await self._copy_agent_snapshot(session, source, target="staging", promoted_by=created_by)
            else:
                if source.snapshot_kind != "staging":
                    raise ConflictError("Agent Staging changed after the promotion preview. Review the promotion again.")
                target = await self._copy_agent_snapshot(session, source, target="release", promoted_by=created_by)
            promoted[action["id"]] = target

        nodes_by_id = {item["node_id"]: item for item in plan["nodes"]}
        final_nodes = []
        resolved_bindings: dict[str, object] = {}
        for node in definition.nodes:
            item = nodes_by_id[str(node.id)]
            release = promoted.get(item.get("action_id"))
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
            final_source = "release" if release.snapshot_kind == "release" else "staging"
            if environment == NetworkEnvironment.PRODUCTION and final_source != "release":
                raise ConflictError("Network Production can only use immutable Agent Releases")
            final_nodes.append(replace(node, binding=AgentBindingSelector(source=final_source, release_id=release.id)))
            resolved_bindings[str(node.id)] = self._release_binding_payload(node.id, node.agent_id, release, final_source)

        final_definition = replace(definition, nodes=tuple(final_nodes), schema_version=2)
        kind = NetworkVersionKind.STAGING if environment == NetworkEnvironment.STAGING else NetworkVersionKind.RELEASE
        final_composition_hash = composition_hash(final_definition, resolved_bindings)
        metadata = await _release_metadata(
            session,
            SimpleNamespace(resolved_bindings=resolved_bindings, composition_hash=final_composition_hash),
            final_definition,
        )
        entry_release = metadata["entry_release"]
        entry_node = next((node for node in final_definition.nodes if node.id == final_definition.root_node_id), None)
        fingerprint_column = getattr(NetworkVersionModel, "release_fingerprint")
        equivalent = await session.scalar(
            select(NetworkVersionModel)
            .where(
                NetworkVersionModel.network_id == network.id,
                NetworkVersionModel.kind == kind.value,
                fingerprint_column == metadata["fingerprint"],
            )
            .order_by(NetworkVersionModel.created_at.desc())
            .limit(1)
        )

        if environment == NetworkEnvironment.STAGING:
            if equivalent is not None:
                network.staging_version_id = equivalent.id
                return equivalent
            existing_versions = list((await session.scalars(select(NetworkVersionModel.version).where(NetworkVersionModel.network_id == network.id, NetworkVersionModel.kind == "staging"))).all())
            version_name = _next_staging_version(existing_versions)
            change_kind = "change"
        else:
            previous = await session.get(NetworkVersionModel, network.production_version_id) if network.production_version_id else None
            release_change = classify_contract_change(
                getattr(previous, "public_output_contract", None) if previous else None,
                metadata["public_contract"],
            )
            change_kind = release_change.value
            if equivalent is not None:
                previous_id = network.production_version_id
                network.production_version_id = equivalent.id
                if previous_id != equivalent.id:
                    session.add(NetworkProductionActivationModel(
                        network_id=network.id,
                        project_id=project_id,
                        version_id=equivalent.id,
                        previous_version_id=previous_id,
                        activation_kind="reactivate",
                        change_description="Equivalent immutable Network Release reused during publish.",
                        created_by=created_by,
                    ))
                return equivalent
            existing_versions = list((await session.scalars(select(NetworkVersionModel.version).where(NetworkVersionModel.network_id == network.id, NetworkVersionModel.kind == "release"))).all())
            version_name = calculate_next_release_version(existing_versions, release_change)

        version = NetworkVersionModel(
            network_id=network.id,
            project_id=project_id,
            kind=kind.value,
            version=version_name,
            definition=final_definition.to_dict(),
            resolved_bindings=resolved_bindings,
            composition_hash=final_composition_hash,
            created_by=created_by,
        )
        setattr(version, "source_draft_revision", network.draft_revision if environment == NetworkEnvironment.STAGING else None)
        setattr(version, "source_staging_version_id", source_version_id if environment == NetworkEnvironment.PRODUCTION else None)
        setattr(version, "entry_agent_id", entry_node.agent_id if entry_node else None)
        setattr(version, "entry_agent_release_id", entry_release.id if entry_release else None)
        setattr(version, "entry_agent_release_version", entry_release.version if entry_release else None)
        setattr(version, "public_output_contract", metadata["public_contract"])
        setattr(version, "public_output_contract_hash", metadata["public_contract_hash"])
        setattr(version, "agent_release_manifest", metadata["manifest"])
        setattr(version, "agent_release_manifest_hash", metadata["manifest_hash"])
        setattr(version, "runtime_settings_hash", metadata["settings_hash"])
        setattr(version, "release_fingerprint", metadata["fingerprint"])
        setattr(version, "change_kind", change_kind)
        if environment == NetworkEnvironment.PRODUCTION:
            version.activation_kind = "publish"
            version.change_description = "Published from the current Network Staging snapshot."
        session.add(version)
        await session.flush()

        if environment == NetworkEnvironment.STAGING:
            network.staging_version_id = version.id
        else:
            previous_id = network.production_version_id
            network.production_version_id = version.id
            session.add(NetworkProductionActivationModel(
                network_id=network.id,
                project_id=project_id,
                version_id=version.id,
                previous_version_id=previous_id,
                activation_kind="publish",
                change_description=version.change_description or "Published Network Release.",
                created_by=created_by,
            ))
        return version


def install_atomic_network_promotion() -> None:
    from modules.network.infra.services.service import NetworkApplicationService

    NetworkApplicationService.promote = _promote_atomic  # type: ignore[assignment]

