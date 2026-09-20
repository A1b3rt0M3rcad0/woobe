from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.agent.domain.external_context_contract import (
    ExternalContextContractError,
    compose_external_context_contracts,
)
from modules.agent.domain.release_versioning import (
    ReleaseChangeKind,
    calculate_next_release_version,
)
from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.network.domain.external_context_contract import (
    classify_effective_external_context_change,
    strongest_release_change,
)
from modules.network.domain.release_contracts import canonical_hash
from modules.network.infra.database.models import (
    NetworkModel,
    NetworkVersionModel,
)
from shared.infra.errors import NotFoundError, ValidationError



def _compose_contracts(contracts: dict[str, Any]) -> dict[str, Any]:
    try:
        return compose_external_context_contracts(contracts)
    except ExternalContextContractError as exc:
        raise ValidationError(str(exc)) from exc


async def compose_effective_contract_from_bindings(
    session: Any,
    bindings: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compose one immutable Network request contract from accepted Agent bindings."""

    contracts: dict[str, Any] = {}
    for consumer, raw_binding in (bindings or {}).items():
        if not isinstance(raw_binding, dict):
            continue
        snapshot_override = raw_binding.get("snapshot_override")
        if isinstance(snapshot_override, dict):
            contracts[str(consumer)] = snapshot_override.get(
                "external_context_contract"
            )
            continue
        release_id = raw_binding.get("release_id")
        if not release_id:
            continue
        release = await session.get(AgentReleaseModel, UUID(str(release_id)))
        if release is not None:
            contracts[str(consumer)] = getattr(
                release,
                "external_context_contract",
                None,
            )
    return _compose_contracts(contracts)


async def _resolve_draft_bindings_with_external_context(
    self,
    session: Any,
    definition: Any,
    project_id: UUID,
) -> dict[str, dict[str, Any]]:
    bindings = await self._external_context_base_resolve_draft_bindings(
        session,
        definition,
        project_id,
    )
    for node in definition.nodes:
        if getattr(node.binding, "source", None) != "draft":
            continue
        binding = bindings.get(str(node.id))
        if not isinstance(binding, dict):
            continue
        snapshot = deepcopy(binding.get("snapshot_override") or {})

        contract = None
        draft_release_id = binding.get("draft_release_id")
        if draft_release_id:
            release = await session.get(AgentReleaseModel, UUID(str(draft_release_id)))
            if release is not None:
                contract = getattr(release, "external_context_contract", None)
        if contract is None:
            agent = await session.get(AgentModel, node.agent_id)
            settings = dict(getattr(agent, "settings", None) or {}) if agent else {}
            contract = settings.get("external_context_contract")

        if contract is not None:
            snapshot["external_context_contract"] = deepcopy(contract)
        else:
            snapshot.pop("external_context_contract", None)
        binding["snapshot_override"] = snapshot
        binding["snapshot_hash"] = self._snapshot_hash(snapshot)
    return bindings


async def _effective_contract_for_plan(
    session: Any,
    nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    bindings: dict[str, Any] = {}
    for item in nodes:
        node_id = str(item.get("node_id") or "").strip()
        selected_ref = item.get("selected_ref")
        if not node_id or not selected_ref:
            continue
        bindings[node_id] = {"release_id": str(selected_ref)}
    return await compose_effective_contract_from_bindings(session, bindings)


async def _preview_with_effective_external_context(
    self,
    *,
    network_id: UUID,
    project_id: UUID,
    environment,
) -> dict[str, Any]:
    plan = await self._external_context_base_preview_promotion(
        network_id=network_id,
        project_id=project_id,
        environment=environment,
    )
    release_preview = plan.get("release_preview")
    if not isinstance(release_preview, dict):
        return plan

    async with self._session_factory() as session:
        network = await session.get(NetworkModel, network_id)
        if network is None or network.project_id != project_id:
            raise NotFoundError("Network not found")
        candidate = await _effective_contract_for_plan(
            session,
            list(plan.get("nodes") or []),
        )
        previous = (
            await session.get(NetworkVersionModel, network.production_version_id)
            if network.production_version_id
            else None
        )
        context_kind = classify_effective_external_context_change(
            previous.effective_external_context_contract if previous else None,
            candidate,
        )
        current_kind = ReleaseChangeKind(
            str(release_preview.get("change_kind") or ReleaseChangeKind.CHANGE.value)
        )
        combined_kind = strongest_release_change(current_kind, context_kind)
        existing_versions = list(
            (
                await session.scalars(
                    select(NetworkVersionModel.version).where(
                        NetworkVersionModel.network_id == network_id,
                        NetworkVersionModel.kind == "release",
                    )
                )
            ).all()
        )

    release_preview["change_kind"] = combined_kind.value
    release_preview["next_version"] = calculate_next_release_version(
        existing_versions,
        combined_kind,
    )
    release_preview["effective_external_context_contract"] = deepcopy(candidate)
    release_preview["effective_external_context_contract_hash"] = canonical_hash(candidate)
    return plan



def install_network_external_context_release_support() -> None:
    from modules.network.infra.services.service import NetworkApplicationService

    if hasattr(NetworkApplicationService, "_external_context_base_preview_promotion"):
        return
    NetworkApplicationService._external_context_base_resolve_draft_bindings = (  # type: ignore[attr-defined]
        NetworkApplicationService._resolve_draft_bindings
    )
    NetworkApplicationService._external_context_base_preview_promotion = (  # type: ignore[attr-defined]
        NetworkApplicationService.preview_promotion
    )
    NetworkApplicationService._resolve_draft_bindings = (  # type: ignore[assignment]
        _resolve_draft_bindings_with_external_context
    )
    NetworkApplicationService.preview_promotion = (  # type: ignore[assignment]
        _preview_with_effective_external_context
    )


__all__ = [
    "compose_effective_contract_from_bindings",
    "install_network_external_context_release_support",
]
