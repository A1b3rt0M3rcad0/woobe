from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.domain.external_context_contract import compose_external_context_contracts
from modules.agent.infra.database.models import AgentReleaseModel
from modules.network.application.runtime import (
    NetworkExecutionSnapshot,
    NetworkVersionSnapshot,
)
from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionModel,
    NetworkVersionModel,
)


_NETWORK_EXTERNAL_CONTEXT_OVERRIDE_KEY = "__network_external_context__"


@dataclass(frozen=True, slots=True)
class LoadedNetworkExecution:
    execution: NetworkExecutionSnapshot
    version: NetworkVersionSnapshot | None
    agent_contexts: dict[str, str | None]


class NetworkRuntimeLoader:
    """Load detached immutable runtime snapshots in one short read-only scope."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _execution_snapshot(
        model: NetworkExecutionModel,
        *,
        resolved_bindings_snapshot: dict | None = None,
    ) -> NetworkExecutionSnapshot:
        return NetworkExecutionSnapshot(
            id=model.id,
            network_id=model.network_id,
            network_version_id=model.network_version_id,
            network_session_id=model.network_session_id,
            project_id=model.project_id,
            input_message=model.input_message,
            draft_revision=model.draft_revision,
            definition_snapshot=deepcopy(model.definition_snapshot),
            resolved_bindings_snapshot=deepcopy(
                resolved_bindings_snapshot
                if resolved_bindings_snapshot is not None
                else model.resolved_bindings_snapshot
            ),
            status=str(model.status),
        )

    @staticmethod
    def _version_snapshot(
        model: NetworkVersionModel,
        *,
        resolved_bindings: dict | None = None,
    ) -> NetworkVersionSnapshot:
        return NetworkVersionSnapshot(
            id=model.id,
            kind=str(model.kind),
            definition=deepcopy(model.definition or {}),
            resolved_bindings=deepcopy(
                resolved_bindings
                if resolved_bindings is not None
                else model.resolved_bindings or {}
            ),
            version=str(model.version) if model.version is not None else None,
        )

    @staticmethod
    def _consumer_values(
        effective_contract: dict,
        consumer: str,
        snapshot: dict,
    ) -> dict:
        fields = effective_contract.get("fields") or {}
        return {
            name: deepcopy(snapshot[name])
            for name, field in fields.items()
            if (
                isinstance(field, dict)
                and isinstance(field.get("consumers"), dict)
                and str(consumer) in field["consumers"]
                and name in snapshot
            )
        }

    @classmethod
    def _bind_external_context(
        cls,
        bindings: dict,
        effective_contract: dict,
        snapshot: dict,
    ) -> dict:
        bound = deepcopy(bindings or {})
        for consumer, raw_binding in bound.items():
            if not isinstance(raw_binding, dict):
                continue
            override = raw_binding.get("snapshot_override")
            runtime_override = deepcopy(override) if isinstance(override, dict) else {}
            runtime_override[_NETWORK_EXTERNAL_CONTEXT_OVERRIDE_KEY] = cls._consumer_values(
                effective_contract,
                str(consumer),
                snapshot,
            )
            raw_binding["snapshot_override"] = runtime_override
        return bound

    @staticmethod
    async def _effective_contract(
        session: AsyncSession,
        *,
        version: NetworkVersionModel | None,
        bindings: dict,
    ) -> dict:
        persisted = (
            getattr(version, "effective_external_context_contract", None)
            if version is not None
            else None
        )
        if isinstance(persisted, dict):
            return deepcopy(persisted)

        contracts: dict[str, object] = {}
        for consumer, binding in (bindings or {}).items():
            if not isinstance(binding, dict):
                continue
            override = binding.get("snapshot_override")
            if isinstance(override, dict):
                contracts[str(consumer)] = override.get("external_context_contract")
                continue
            release_id = binding.get("release_id")
            if release_id:
                release = await session.get(AgentReleaseModel, UUID(str(release_id)))
                if release is not None:
                    contracts[str(consumer)] = getattr(
                        release,
                        "external_context_contract",
                        None,
                    )
        return compose_external_context_contracts(contracts)

    async def load(self, execution_id: UUID) -> LoadedNetworkExecution | None:
        async with self._session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            if execution is None:
                return None
            version = (
                await session.get(NetworkVersionModel, execution.network_version_id)
                if execution.network_version_id
                else None
            )

            source_bindings = (
                version.resolved_bindings or {}
                if version is not None
                else execution.resolved_bindings_snapshot or {}
            )
            effective_contract = await self._effective_contract(
                session,
                version=version,
                bindings=source_bindings,
            )
            external_context_snapshot = deepcopy(
                getattr(execution, "external_context_snapshot", None) or {}
            )
            runtime_bindings = self._bind_external_context(
                source_bindings,
                effective_contract,
                external_context_snapshot,
            )

            result = await session.execute(
                select(NetworkAgentContextModel).where(
                    NetworkAgentContextModel.network_session_id
                    == execution.network_session_id
                )
            )
            contexts = {
                str(item.network_node_id): (
                    str(item.agent_session_id) if item.agent_session_id else None
                )
                for item in result.scalars()
            }
            return LoadedNetworkExecution(
                execution=self._execution_snapshot(
                    execution,
                    resolved_bindings_snapshot=(
                        runtime_bindings if version is None else None
                    ),
                ),
                version=(
                    self._version_snapshot(version, resolved_bindings=runtime_bindings)
                    if version is not None
                    else None
                ),
                agent_contexts=contexts,
            )

    async def recovery_candidates(
        self,
        *,
        older_than_seconds: int,
        limit: int = 50,
    ) -> list[UUID]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)
        async with self._session_factory() as session:
            result = await session.execute(
                select(NetworkExecutionModel.id)
                .where(
                    NetworkExecutionModel.status.in_([
                        "queued",
                        "running",
                        "cancel_requested",
                    ]),
                    NetworkExecutionModel.created_at < cutoff,
                )
                .order_by(NetworkExecutionModel.created_at.asc())
                .limit(limit)
            )
            return list(result.scalars())