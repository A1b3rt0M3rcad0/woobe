from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from modules.network.application.dtos.management import ManagedNetworkVersion
from modules.network.application.dtos.promotion import (
    CreateNetworkPromotionVersionInput,
    PromoteNetworkInput,
    PreviewNetworkPromotionInput,
)
from modules.network.application.interfaces.agent_promotion import (
    AgentPromotionGateway,
    AgentSnapshot,
)
from modules.network.application.interfaces.promotion_repository import (
    NetworkPromotionRepository,
)
from modules.network.domain.entities import (
    AgentBindingSelector,
    Network,
    NetworkDefinition,
    NetworkNode,
)
from modules.network.domain.enums import NetworkEnvironment, NetworkVersionKind
from modules.network.domain.graph import composition_hash, validate_network_definition
from modules.network.domain.release_contracts import (
    canonical_hash,
    classify_contract_change,
    output_contract_hash,
    output_contract_snapshot,
    runtime_settings_hash,
)
from modules.network.domain.release_versioning import calculate_next_release_version
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError


_VALID_SESSION_MODES = {"stateful", "stateless"}


@dataclass(slots=True)
class _NodePlan:
    node: NetworkNode
    selected_source: str
    result_source: str
    selected: AgentSnapshot | None
    result: AgentSnapshot | None
    action_required: str | None = None
    action_id: str | None = None
    blocking_reason: str | None = None
    reuse_reason: str | None = None
    result_resolution: str = "retained"


@dataclass(slots=True)
class _PromotionPlan:
    network: Network
    source_version: ManagedNetworkVersion | None
    definition: NetworkDefinition
    nodes: list[_NodePlan]


class NetworkPromotionPlanner:
    def __init__(
        self,
        repository: NetworkPromotionRepository,
        agent_gateway: AgentPromotionGateway,
        *,
        hard_max_depth: int,
        hard_max_invocations: int,
        hard_timeout_seconds: int,
    ) -> None:
        self._repository = repository
        self._agent_gateway = agent_gateway
        self._hard_max_depth = hard_max_depth
        self._hard_max_invocations = hard_max_invocations
        self._hard_timeout_seconds = hard_timeout_seconds

    async def build(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: NetworkEnvironment,
        lock: bool,
    ) -> _PromotionPlan:
        if environment not in {
            NetworkEnvironment.STAGING,
            NetworkEnvironment.PRODUCTION,
        }:
            raise ValidationError("Draft cannot be promoted as a runtime environment")

        network = await self._repository.get_network(
            network_id=network_id,
            project_id=project_id,
            lock=lock,
        )
        if network is None:
            raise NotFoundError("Network not found")

        source_version: ManagedNetworkVersion | None = None
        if environment == NetworkEnvironment.STAGING:
            definition = self._definition(network.draft_definition)
            nodes = await self._plan_staging_nodes(
                definition=definition,
                project_id=project_id,
                lock=lock,
            )
        else:
            if network.staging_version_id is None:
                raise ConflictError("Stage the Network before publishing Production")
            source_version = await self._repository.get_version(
                version_id=network.staging_version_id,
                project_id=project_id,
                network_id=network.id,
                lock=lock,
            )
            if source_version is None or source_version.kind != "staging":
                raise ConflictError("Current Network Staging version was not found")
            definition = self._definition(source_version.definition)
            nodes = await self._plan_production_nodes(
                definition=definition,
                resolved_bindings=source_version.resolved_bindings,
                project_id=project_id,
                lock=lock,
            )

        return _PromotionPlan(
            network=network,
            source_version=source_version,
            definition=definition,
            nodes=nodes,
        )

    async def preview_payload(
        self,
        plan: _PromotionPlan,
        environment: NetworkEnvironment,
    ) -> dict[str, Any]:
        actions: list[dict[str, Any]] = []
        nodes: list[dict[str, Any]] = []
        bindings: dict[str, dict[str, Any]] = {}
        missing_agent_ids: list[str] = []
        seen_actions: set[str] = set()

        for item in plan.nodes:
            selected = item.selected
            result = item.result
            if item.blocking_reason:
                missing_agent_ids.append(str(item.node.agent_id))
            if item.action_id and item.action_id not in seen_actions:
                seen_actions.add(item.action_id)
                actions.append(
                    {
                        "id": item.action_id,
                        "agent_id": str(item.node.agent_id),
                        "agent_name": self._agent_name(item),
                        "action": item.action_required,
                        "source_release_id": str(selected.id) if selected else "",
                        "source_version": selected.version if selected else "draft",
                        "source_snapshot_hash": (
                            self._agent_gateway.snapshot_hash(selected)
                            if selected is not None
                            else None
                        ),
                    }
                )
            nodes.append(
                {
                    "node_id": str(item.node.id),
                    "agent_id": str(item.node.agent_id),
                    "agent_name": self._agent_name(item),
                    "selected_source": item.selected_source,
                    "selected_ref": str(selected.id) if selected else None,
                    "selected_version": selected.version if selected else None,
                    "source_ref": str(selected.id) if selected else None,
                    "source_version": selected.version if selected else None,
                    "result_source": item.result_source,
                    "result_ref": str(result.id) if result else None,
                    "result_version": result.version if result else None,
                    "result_will_be_created": bool(item.action_required),
                    "result_resolution": item.result_resolution,
                    "action_required": item.action_required,
                    "action_id": item.action_id,
                    "blocking_reason": item.blocking_reason,
                    "reuse_reason": item.reuse_reason,
                    "snapshot_hash": (
                        self._agent_gateway.snapshot_hash(selected)
                        if selected is not None
                        else None
                    ),
                }
            )
            binding_snapshot = result or selected
            bindings[str(item.node.id)] = {
                "node_id": str(item.node.id),
                "agent_id": str(item.node.agent_id),
                "binding_source": item.result_source,
                "release_id": str(result.id) if result else None,
                "release_version": result.version if result else None,
                "snapshot_hash": (
                    self._agent_gateway.snapshot_hash(binding_snapshot)
                    if binding_snapshot is not None
                    else None
                ),
            }

        counts = self._counts(plan.nodes)
        payload: dict[str, Any] = {
            "environment": environment.value,
            "network_revision": plan.network.draft_revision,
            "network_version_id": (
                str(plan.source_version.id) if plan.source_version else None
            ),
            "ready": not missing_agent_ids,
            "nodes": nodes,
            "actions": actions,
            "bindings": bindings,
            "missing_agent_ids": list(dict.fromkeys(missing_agent_ids)),
            "reused_agent_count": counts["equivalent_snapshots_reused"]
            + counts["staging_retained"]
            + counts["releases_retained"],
            **counts,
        }

        if environment == NetworkEnvironment.STAGING:
            versions = await self._repository.list_version_names(
                plan.network.id,
                "staging",
            )
            payload["staging_preview"] = {
                "next_version": _next_staging_version(versions),
                "reused_agent_count": payload["reused_agent_count"],
                "promotion_count": len(actions),
                **counts,
            }
        else:
            payload["release_preview"] = await self._release_preview(
                plan,
                actions=actions,
                counts=counts,
            )
        return payload

    async def _plan_staging_nodes(
        self,
        *,
        definition: NetworkDefinition,
        project_id: UUID,
        lock: bool,
    ) -> list[_NodePlan]:
        plans: list[_NodePlan] = []
        for node in definition.nodes:
            active = await self._agent_gateway.is_active_agent(
                project_id=project_id,
                agent_id=node.agent_id,
            )
            if not active:
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source=node.binding.source,
                        result_source=(
                            "staging" if node.binding.source == "draft" else node.binding.source
                        ),
                        selected=None,
                        result=None,
                        blocking_reason=f"Agent is unavailable: {node.agent_id}",
                        result_resolution="blocked",
                    )
                )
                continue

            if node.binding.source == "draft":
                draft = await self._agent_gateway.latest_draft(
                    project_id=project_id,
                    agent_id=node.agent_id,
                    lock=lock,
                )
                if draft is None:
                    plans.append(
                        _NodePlan(
                            node=node,
                            selected_source="draft",
                            result_source="staging",
                            selected=None,
                            result=None,
                            blocking_reason=(
                                "Save the Agent Draft before staging the Network"
                            ),
                            result_resolution="blocked",
                        )
                    )
                    continue
                equivalent = await self._agent_gateway.equivalent_snapshot(
                    source=draft,
                    target_kind="staging",
                    active_only=True,
                    lock=lock,
                )
                if equivalent is not None:
                    plans.append(
                        _NodePlan(
                            node=node,
                            selected_source="draft",
                            result_source="staging",
                            selected=draft,
                            result=equivalent,
                            reuse_reason=(
                                "Current Agent Staging already matches the saved Draft."
                            ),
                            result_resolution="equivalent_reused",
                        )
                    )
                    continue
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source="draft",
                        result_source="staging",
                        selected=draft,
                        result=None,
                        action_required="promote_draft_to_staging",
                        action_id=self._action_id("stage", draft),
                        result_resolution="promoted",
                    )
                )
                continue

            selected = await self._agent_gateway.snapshot_by_id(
                release_id=node.binding.release_id,
                project_id=project_id,
                agent_id=node.agent_id,
                lock=lock,
            )
            if selected is None or selected.snapshot_kind != node.binding.source:
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source=node.binding.source,
                        result_source=node.binding.source,
                        selected=None,
                        result=None,
                        blocking_reason=(
                            f"Selected Agent {node.binding.source.title()} snapshot is unavailable."
                        ),
                        result_resolution="blocked",
                    )
                )
                continue
            plans.append(
                _NodePlan(
                    node=node,
                    selected_source=node.binding.source,
                    result_source=node.binding.source,
                    selected=selected,
                    result=selected,
                )
            )
        return plans

    async def _plan_production_nodes(
        self,
        *,
        definition: NetworkDefinition,
        resolved_bindings: dict[str, Any],
        project_id: UUID,
        lock: bool,
    ) -> list[_NodePlan]:
        plans: list[_NodePlan] = []
        for node in definition.nodes:
            binding = resolved_bindings.get(str(node.id)) or {}
            source_name = str(
                binding.get("binding_source") or node.binding.source or "staging"
            )
            raw_release_id = binding.get("release_id") or node.binding.release_id
            try:
                release_id = UUID(str(raw_release_id)) if raw_release_id else None
            except (TypeError, ValueError):
                release_id = None
            selected = await self._agent_gateway.snapshot_by_id(
                release_id=release_id,
                project_id=project_id,
                agent_id=node.agent_id,
                lock=lock,
            )
            if selected is None:
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source=source_name,
                        result_source="release",
                        selected=None,
                        result=None,
                        blocking_reason=(
                            "Agent snapshot pinned by Network Staging is unavailable."
                        ),
                        result_resolution="blocked",
                    )
                )
                continue
            if selected.snapshot_kind == "release":
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source="release",
                        result_source="release",
                        selected=selected,
                        result=selected,
                    )
                )
                continue
            if selected.snapshot_kind != "staging":
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source=selected.snapshot_kind,
                        result_source="release",
                        selected=selected,
                        result=None,
                        blocking_reason=(
                            "Network Staging contains an invalid Agent snapshot kind."
                        ),
                        result_resolution="blocked",
                    )
                )
                continue
            equivalent = await self._agent_gateway.equivalent_snapshot(
                source=selected,
                target_kind="release",
                active_only=False,
                lock=lock,
            )
            if equivalent is not None:
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source="staging",
                        result_source="release",
                        selected=selected,
                        result=equivalent,
                        reuse_reason=(
                            "An immutable Agent Release already matches this Staging snapshot."
                        ),
                        result_resolution="equivalent_reused",
                    )
                )
                continue
            plans.append(
                _NodePlan(
                    node=node,
                    selected_source="staging",
                    result_source="release",
                    selected=selected,
                    result=None,
                    action_required="publish_staging_to_release",
                    action_id=self._action_id("release", selected),
                    result_resolution="promoted",
                )
            )
        return plans

    async def _release_preview(
        self,
        plan: _PromotionPlan,
        *,
        actions: list[dict[str, Any]],
        counts: dict[str, int],
    ) -> dict[str, Any]:
        manifest, entry_snapshot = self._manifest_from_plan(plan)
        candidate_contract = (
            output_contract_snapshot(entry_snapshot) if entry_snapshot is not None else None
        )
        previous = None
        if plan.network.production_version_id is not None:
            previous = await self._repository.get_version(
                version_id=plan.network.production_version_id,
                project_id=plan.network.project_id,
                network_id=plan.network.id,
                lock=False,
            )
        previous_contract = (
            previous.extensions.get("public_output_contract") if previous else None
        )
        change_kind = classify_contract_change(previous_contract, candidate_contract)
        versions = await self._repository.list_version_names(plan.network.id, "release")

        previous_manifest = {
            str(item.get("node_id")): item
            for item in (
                previous.extensions.get("agent_release_manifest") or []
                if previous
                else []
            )
        }
        internal_warnings: list[str] = []
        for item in manifest:
            if item["role"] == "entry":
                continue
            before = previous_manifest.get(item["node_id"])
            if before and before.get("output_contract_hash") != item["output_contract_hash"]:
                internal_warnings.append(
                    f"Specialist Agent {item['agent_id']} changed its internal output contract."
                )

        return {
            "change_kind": change_kind.value,
            "next_version": calculate_next_release_version(versions, change_kind),
            "entry_agent_id": (
                str(entry_snapshot.agent_id) if entry_snapshot is not None else None
            ),
            "entry_agent_release_id": (
                str(entry_snapshot.id) if entry_snapshot is not None else None
            ),
            "entry_agent_release_version": (
                entry_snapshot.version if entry_snapshot is not None else None
            ),
            "public_output_contract": candidate_contract,
            "public_output_contract_hash": canonical_hash(candidate_contract),
            "agent_release_manifest": manifest,
            "internal_warnings": internal_warnings,
            "reused_agent_count": counts["equivalent_snapshots_reused"]
            + counts["releases_retained"],
            "promotion_count": len(actions),
            "agent_productions_changed": 0,
            **counts,
        }

    def _manifest_from_plan(
        self,
        plan: _PromotionPlan,
    ) -> tuple[list[dict[str, Any]], AgentSnapshot | None]:
        manifest: list[dict[str, Any]] = []
        entry_snapshot: AgentSnapshot | None = None
        for item in plan.nodes:
            snapshot = item.result or item.selected
            if snapshot is None:
                continue
            role = "entry" if item.node.id == plan.definition.root_node_id else "specialist"
            manifest.append(
                {
                    "node_id": str(item.node.id),
                    "role": role,
                    "agent_id": str(item.node.agent_id),
                    "release_id": str(snapshot.id),
                    "release_version": snapshot.version,
                    "snapshot_hash": self._agent_gateway.snapshot_hash(snapshot),
                    "output_contract_hash": output_contract_hash(snapshot),
                }
            )
            if role == "entry":
                entry_snapshot = snapshot
        manifest.sort(key=lambda value: (value["role"] != "entry", value["node_id"]))
        return manifest, entry_snapshot

    def _definition(self, raw: dict[str, Any]) -> NetworkDefinition:
        try:
            definition = NetworkDefinition.from_dict(raw)
            validate_network_definition(
                definition,
                hard_max_depth=self._hard_max_depth,
                hard_max_invocations=self._hard_max_invocations,
                hard_timeout_seconds=self._hard_timeout_seconds,
            )
            return definition
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(str(exc)) from exc

    def _action_id(self, prefix: str, snapshot: AgentSnapshot) -> str:
        return (
            f"{prefix}:{snapshot.agent_id}:{snapshot.id}:"
            f"{self._agent_gateway.snapshot_hash(snapshot)[:16]}"
        )

    @staticmethod
    def _agent_name(item: _NodePlan) -> str:
        snapshot = item.selected or item.result
        return snapshot.name if snapshot is not None and snapshot.name else item.node.label

    @staticmethod
    def _counts(nodes: list[_NodePlan]) -> dict[str, int]:
        return {
            "draft_promotions": sum(
                1 for item in nodes if item.action_required == "promote_draft_to_staging"
            ),
            "staging_retained": sum(
                1
                for item in nodes
                if item.result_source == "staging"
                and item.action_required is None
                and item.result_resolution == "retained"
            ),
            "release_promotions": sum(
                1 for item in nodes if item.action_required == "publish_staging_to_release"
            ),
            "releases_retained": sum(
                1
                for item in nodes
                if item.result_source == "release"
                and item.action_required is None
                and item.result_resolution == "retained"
            ),
            "equivalent_snapshots_reused": sum(
                1 for item in nodes if item.result_resolution == "equivalent_reused"
            ),
        }


class PreviewNetworkPromotionUseCase:
    def __init__(self, planner: NetworkPromotionPlanner) -> None:
        self._planner = planner

    async def execute(self, input_dto: PreviewNetworkPromotionInput) -> dict[str, Any]:
        plan = await self._planner.build(
            network_id=input_dto.network_id,
            project_id=input_dto.project_id,
            environment=input_dto.environment,
            lock=False,
        )
        return await self._planner.preview_payload(plan, input_dto.environment)


class PromoteNetworkUseCase:
    def __init__(
        self,
        planner: NetworkPromotionPlanner,
        repository: NetworkPromotionRepository,
        agent_gateway: AgentPromotionGateway,
    ) -> None:
        self._planner = planner
        self._repository = repository
        self._agent_gateway = agent_gateway

    async def execute(self, input_dto: PromoteNetworkInput) -> ManagedNetworkVersion:
        plan = await self._planner.build(
            network_id=input_dto.network_id,
            project_id=input_dto.project_id,
            environment=input_dto.environment,
            lock=True,
        )
        self._check_concurrency(plan, input_dto)

        blocked = [item for item in plan.nodes if item.blocking_reason]
        if blocked:
            raise ConflictError(
                blocked[0].blocking_reason or "Network promotion is blocked"
            )

        required = {item.action_id for item in plan.nodes if item.action_id}
        approved = set(input_dto.approved_action_ids)
        if not required.issubset(approved):
            raise ConflictError(
                "Agent promotion approvals changed. Review the promotion again."
            )

        promoted: dict[str, AgentSnapshot] = {}
        for item in plan.nodes:
            if item.action_id is None:
                continue
            if item.selected is None:
                raise ConflictError("Agent snapshot selected for promotion was not found")
            if item.action_required == "promote_draft_to_staging":
                promoted[item.action_id] = (
                    await self._agent_gateway.promote_draft_to_staging(
                        item.selected,
                        user_id=input_dto.created_by,
                    )
                )
            elif item.action_required == "publish_staging_to_release":
                promoted[item.action_id] = (
                    await self._agent_gateway.publish_staging_for_network(
                        item.selected,
                        user_id=input_dto.created_by,
                    )
                )

        final_nodes: list[NetworkNode] = []
        final_snapshots: dict[str, AgentSnapshot] = {}
        resolved_bindings: dict[str, dict[str, Any]] = {}
        for item in plan.nodes:
            snapshot = (
                promoted.get(item.action_id) if item.action_id is not None else None
            ) or item.result or item.selected
            if snapshot is None:
                raise ConflictError(
                    f"Agent snapshot could not be resolved: {item.node.agent_id}"
                )
            final_source = "release" if snapshot.snapshot_kind == "release" else "staging"
            if (
                input_dto.environment == NetworkEnvironment.PRODUCTION
                and final_source != "release"
            ):
                raise ConflictError(
                    "Network Production can only use immutable Agent Releases"
                )
            session_mode = _session_mode(snapshot.session_mode)
            if session_mode is None:
                raise ConflictError(
                    f"Agent snapshot has no valid Session Mode: {item.node.id}"
                )
            final_nodes.append(
                replace(
                    item.node,
                    binding=AgentBindingSelector(
                        source=final_source,
                        release_id=snapshot.id,
                    ),
                )
            )
            final_snapshots[str(item.node.id)] = snapshot
            resolved_bindings[str(item.node.id)] = {
                "node_id": str(item.node.id),
                "agent_id": str(item.node.agent_id),
                "binding_source": final_source,
                "release_id": str(snapshot.id),
                "release_version": snapshot.version,
                "release_status": _enum_value(snapshot.status),
                "snapshot_kind": snapshot.snapshot_kind,
                "snapshot_hash": self._agent_gateway.snapshot_hash(snapshot),
                "session_mode": session_mode,
            }

        final_definition = replace(
            plan.definition,
            nodes=tuple(final_nodes),
            schema_version=2,
        )
        final_hash = composition_hash(final_definition, resolved_bindings)
        metadata = self._release_metadata(
            final_definition,
            final_snapshots,
            final_hash,
        )
        kind = (
            NetworkVersionKind.STAGING.value
            if input_dto.environment == NetworkEnvironment.STAGING
            else NetworkVersionKind.RELEASE.value
        )
        equivalent = await self._repository.find_by_fingerprint(
            network_id=plan.network.id,
            kind=kind,
            fingerprint=metadata["fingerprint"],
        )
        if equivalent is not None:
            if input_dto.environment == NetworkEnvironment.STAGING:
                await self._repository.set_staging_version(plan.network.id, equivalent.id)
            else:
                previous_id = plan.network.production_version_id
                await self._repository.set_production_version(plan.network.id, equivalent.id)
                if previous_id != equivalent.id:
                    await self._repository.record_activation(
                        network_id=plan.network.id,
                        project_id=input_dto.project_id,
                        version_id=equivalent.id,
                        previous_version_id=previous_id,
                        activation_kind="reactivate",
                        change_description=(
                            "Equivalent immutable Network Release reused during publish."
                        ),
                        created_by=input_dto.created_by,
                    )
            return equivalent

        previous = None
        change_kind = "change"
        activation_kind = None
        change_description = None
        if input_dto.environment == NetworkEnvironment.STAGING:
            existing = await self._repository.list_version_names(plan.network.id, kind)
            version_name = _next_staging_version(existing)
        else:
            if plan.network.production_version_id is not None:
                previous = await self._repository.get_version(
                    version_id=plan.network.production_version_id,
                    project_id=input_dto.project_id,
                    network_id=plan.network.id,
                    lock=True,
                )
            previous_contract = (
                previous.extensions.get("public_output_contract") if previous else None
            )
            release_change = classify_contract_change(
                previous_contract,
                metadata["public_contract"],
            )
            change_kind = release_change.value
            existing = await self._repository.list_version_names(plan.network.id, kind)
            version_name = calculate_next_release_version(existing, release_change)
            activation_kind = "publish"
            change_description = "Published from the current Network Staging snapshot."

        created = await self._repository.create_version(
            CreateNetworkPromotionVersionInput(
                network_id=plan.network.id,
                project_id=input_dto.project_id,
                kind=kind,
                version=version_name,
                definition=final_definition.to_dict(),
                resolved_bindings=resolved_bindings,
                composition_hash=final_hash,
                created_by=input_dto.created_by,
                source_draft_revision=(
                    plan.network.draft_revision
                    if input_dto.environment == NetworkEnvironment.STAGING
                    else None
                ),
                source_staging_version_id=(
                    plan.source_version.id if plan.source_version is not None else None
                ),
                entry_agent_id=metadata["entry_agent_id"],
                entry_agent_release_id=metadata["entry_agent_release_id"],
                entry_agent_release_version=metadata["entry_agent_release_version"],
                public_output_contract=metadata["public_contract"],
                public_output_contract_hash=metadata["public_contract_hash"],
                agent_release_manifest=metadata["manifest"],
                agent_release_manifest_hash=metadata["manifest_hash"],
                runtime_settings_hash=metadata["settings_hash"],
                release_fingerprint=metadata["fingerprint"],
                change_kind=change_kind,
                activation_kind=activation_kind,
                change_description=change_description,
            )
        )
        if input_dto.environment == NetworkEnvironment.STAGING:
            await self._repository.set_staging_version(plan.network.id, created.id)
        else:
            previous_id = plan.network.production_version_id
            await self._repository.set_production_version(plan.network.id, created.id)
            await self._repository.record_activation(
                network_id=plan.network.id,
                project_id=input_dto.project_id,
                version_id=created.id,
                previous_version_id=previous_id,
                activation_kind="publish",
                change_description=change_description or "Published Network Release.",
                created_by=input_dto.created_by,
            )
        return created

    @staticmethod
    def _check_concurrency(
        plan: _PromotionPlan,
        input_dto: PromoteNetworkInput,
    ) -> None:
        if (
            input_dto.environment == NetworkEnvironment.STAGING
            and input_dto.expected_revision is not None
            and input_dto.expected_revision != plan.network.draft_revision
        ):
            raise ConflictError(
                "Network Draft changed after the promotion preview. Review the promotion again."
            )
        source_id = plan.source_version.id if plan.source_version is not None else None
        if (
            input_dto.environment == NetworkEnvironment.PRODUCTION
            and input_dto.expected_network_version_id is not None
            and input_dto.expected_network_version_id != source_id
        ):
            raise ConflictError(
                "Network Staging changed after the promotion preview. Review the promotion again."
            )

    def _release_metadata(
        self,
        definition: NetworkDefinition,
        snapshots: dict[str, AgentSnapshot],
        composition_hash_value: str,
    ) -> dict[str, Any]:
        manifest: list[dict[str, Any]] = []
        entry_snapshot: AgentSnapshot | None = None
        for node in definition.nodes:
            snapshot = snapshots[str(node.id)]
            role = "entry" if node.id == definition.root_node_id else "specialist"
            manifest.append(
                {
                    "node_id": str(node.id),
                    "role": role,
                    "agent_id": str(node.agent_id),
                    "release_id": str(snapshot.id),
                    "release_version": snapshot.version,
                    "snapshot_hash": self._agent_gateway.snapshot_hash(snapshot),
                    "output_contract_hash": output_contract_hash(snapshot),
                }
            )
            if role == "entry":
                entry_snapshot = snapshot
        manifest.sort(key=lambda item: (item["role"] != "entry", item["node_id"]))
        public_contract = (
            output_contract_snapshot(entry_snapshot) if entry_snapshot is not None else None
        )
        public_contract_hash = canonical_hash(public_contract)
        manifest_hash = canonical_hash(manifest)
        settings_hash = runtime_settings_hash(definition)
        fingerprint = canonical_hash(
            {
                "composition_hash": composition_hash_value,
                "public_output_contract_hash": public_contract_hash,
                "agent_release_manifest_hash": manifest_hash,
                "runtime_settings_hash": settings_hash,
            }
        )
        return {
            "entry_agent_id": (
                entry_snapshot.agent_id if entry_snapshot is not None else None
            ),
            "entry_agent_release_id": (
                entry_snapshot.id if entry_snapshot is not None else None
            ),
            "entry_agent_release_version": (
                entry_snapshot.version if entry_snapshot is not None else None
            ),
            "public_contract": public_contract,
            "public_contract_hash": public_contract_hash,
            "manifest": manifest,
            "manifest_hash": manifest_hash,
            "settings_hash": settings_hash,
            "fingerprint": fingerprint,
        }


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


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _session_mode(value: Any) -> str | None:
    normalized = _enum_value(value)
    return normalized if normalized in _VALID_SESSION_MODES else None
