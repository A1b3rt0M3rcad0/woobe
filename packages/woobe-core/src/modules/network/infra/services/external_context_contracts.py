from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.agent.domain.external_context_contract import (
    ExternalContextContractError,
    compose_external_context_contracts,
)
from modules.agent.domain.release_versioning import calculate_next_release_version
from modules.agent.infra.database.models import AgentReleaseModel
from modules.network.domain.external_context_contract import (
    classify_effective_external_context_change,
    strongest_release_change,
)
from modules.network.domain.release_contracts import classify_contract_change
from modules.network.infra.database.models import (
    NetworkProductionActivationModel,
    NetworkVersionModel,
)
from shared.infra.errors import ValidationError


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
    try:
        return compose_external_context_contracts(contracts)
    except ExternalContextContractError as exc:
        raise ValidationError(str(exc)) from exc


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


def install_network_external_context_release_support() -> None:
    from modules.network.infra.services.service import NetworkApplicationService

    if hasattr(NetworkApplicationService, "_external_context_base_promote"):
        return
    NetworkApplicationService._external_context_base_promote = (  # type: ignore[attr-defined]
        NetworkApplicationService.promote
    )
    NetworkApplicationService.promote = _promote_with_effective_external_context  # type: ignore[assignment]


__all__ = ["install_network_external_context_release_support"]
