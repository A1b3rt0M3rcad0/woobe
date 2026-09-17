from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select

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
from modules.network.domain.release_contracts import canonical_hash, classify_contract_change
from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionModel,
    NetworkModel,
    NetworkProductionActivationModel,
    NetworkSessionModel,
    NetworkVersionModel,
)
from shared.infra.errors import ConflictError, NotFoundError, ValidationError


_ACTIVE_STATUSES = {"queued", "running", "cancel_requested"}


def _compose_contracts(contracts: dict[str, Any]) -> dict[str, Any]:
    try:
        return compose_external_context_contracts(contracts)
    except ExternalContextContractError as exc:
        raise ValidationError(str(exc)) from exc


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


async def _effective_contract_for_version(
    session: Any,
    version: NetworkVersionModel,
    definition: Any,
) -> dict[str, Any]:
    contracts: dict[str, Any] = {}
    bindings = version.resolved_bindings or {}
    for node in definition.nodes:
        binding = bindings.get(str(node.id)) or {}
        release_id = binding.get("release_id")
        if not release_id:
            continue
        release = await session.get(AgentReleaseModel, UUID(str(release_id)))
        if release is None:
            continue
        contracts[str(node.id)] = getattr(release, "external_context_contract", None)
    return _compose_contracts(contracts)


async def _effective_contract_for_plan(
    session: Any,
    nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    contracts: dict[str, Any] = {}
    for item in nodes:
        node_id = str(item.get("node_id") or "").strip()
        selected_ref = item.get("selected_ref")
        if not node_id or not selected_ref:
            continue
        release = await session.get(AgentReleaseModel, UUID(str(selected_ref)))
        if release is None:
            continue
        contracts[node_id] = getattr(release, "external_context_contract", None)
    return _compose_contracts(contracts)


async def _latest_activation(
    session: Any,
    *,
    network_id: UUID,
    version_id: UUID,
):
    return await session.scalar(
        select(NetworkProductionActivationModel)
        .where(
            NetworkProductionActivationModel.network_id == network_id,
            NetworkProductionActivationModel.version_id == version_id,
        )
        .order_by(NetworkProductionActivationModel.created_at.desc())
        .limit(1)
    )


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


async def _promote_with_effective_external_context(
    self,
    *,
    network_id: UUID,
    project_id: UUID,
    environment,
    created_by: UUID | None,
    expected_revision: int | None = None,
    expected_network_version_id: UUID | None = None,
    approved_action_ids: list[str] | None = None,
):
    created = await self._external_context_base_promote(
        network_id=network_id,
        project_id=project_id,
        environment=environment,
        created_by=created_by,
        expected_revision=expected_revision,
        expected_network_version_id=expected_network_version_id,
        approved_action_ids=approved_action_ids,
    )

    async with self._session_factory() as session, session.begin():
        version = await session.get(NetworkVersionModel, created.id, with_for_update=True)
        if version is None:
            return created

        definition = self._definition(version.definition)
        effective = await _effective_contract_for_version(session, version, definition)
        version.effective_external_context_contract = deepcopy(effective)

        # Production Network versioning must reflect both public output compatibility and
        # the request-side External Context boundary. Staging keeps its revision semantics.
        if str(version.kind) == "release":
            activation = await _latest_activation(
                session,
                network_id=network_id,
                version_id=version.id,
            )
            previous = (
                await session.get(NetworkVersionModel, activation.previous_version_id)
                if activation is not None and activation.previous_version_id is not None
                else None
            )
            output_kind = classify_contract_change(
                previous.public_output_contract if previous else None,
                version.public_output_contract,
            )
            context_kind = classify_effective_external_context_change(
                previous.effective_external_context_contract if previous else None,
                effective,
            )
            change_kind = strongest_release_change(output_kind, context_kind)
            version.change_kind = change_kind.value

            # A reactivation/rollback points at an already immutable historical Release;
            # never rename it. New publishes can safely receive the stronger semantic bump.
            activation_kind = str(getattr(activation, "activation_kind", "") or "")
            if activation_kind == "publish":
                existing_versions = list(
                    (
                        await session.scalars(
                            select(NetworkVersionModel.version).where(
                                NetworkVersionModel.network_id == network_id,
                                NetworkVersionModel.kind == "release",
                                NetworkVersionModel.id != version.id,
                            )
                        )
                    ).all()
                )
                version.version = calculate_next_release_version(
                    existing_versions,
                    change_kind,
                )

        await session.flush()
        created.effective_external_context_contract = deepcopy(effective)
        created.change_kind = version.change_kind
        created.version = version.version
        return created


async def _reset_session_context_with_external_context(
    self,
    *,
    network_id: UUID,
    network_session_id: UUID,
    project_id: UUID,
) -> None:
    async with self._session_factory() as session, session.begin():
        network_session = await session.get(
            NetworkSessionModel,
            network_session_id,
            with_for_update=True,
        )
        if (
            network_session is None
            or network_session.network_id != network_id
            or network_session.project_id != project_id
        ):
            raise NotFoundError("Network Session not found")
        active = await session.scalar(
            select(NetworkExecutionModel.id).where(
                NetworkExecutionModel.network_session_id == network_session_id,
                NetworkExecutionModel.status.in_(_ACTIVE_STATUSES),
            )
        )
        if active is not None:
            raise ConflictError("Wait for the active execution before resetting context")

        network_session.external_context_session_values = None
        await session.execute(
            delete(NetworkAgentContextModel).where(
                NetworkAgentContextModel.network_session_id == network_session_id
            )
        )


def install_network_external_context_release_support() -> None:
    from modules.network.infra.services.service import NetworkApplicationService

    if hasattr(NetworkApplicationService, "_external_context_base_promote"):
        return
    NetworkApplicationService._external_context_base_resolve_draft_bindings = (  # type: ignore[attr-defined]
        NetworkApplicationService._resolve_draft_bindings
    )
    NetworkApplicationService._external_context_base_preview_promotion = (  # type: ignore[attr-defined]
        NetworkApplicationService.preview_promotion
    )
    NetworkApplicationService._external_context_base_promote = (  # type: ignore[attr-defined]
        NetworkApplicationService.promote
    )
    NetworkApplicationService._resolve_draft_bindings = (  # type: ignore[assignment]
        _resolve_draft_bindings_with_external_context
    )
    NetworkApplicationService.preview_promotion = (  # type: ignore[assignment]
        _preview_with_effective_external_context
    )
    NetworkApplicationService.promote = _promote_with_effective_external_context  # type: ignore[assignment]
    NetworkApplicationService.reset_session_context = (  # type: ignore[assignment]
        _reset_session_context_with_external_context
    )


__all__ = ["install_network_external_context_release_support"]
