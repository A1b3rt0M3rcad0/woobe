from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.models import AgentReleaseModel, AgentToolModel
from modules.evaluation.application.target_resolver import ResolvedEvaluationTarget
from shared.infra.errors import ConflictError


@dataclass(frozen=True)
class ToolRiskItem:
    id: UUID
    name: str
    risk_level: str
    source: str


@dataclass(frozen=True)
class EvaluationPreflight:
    tools: tuple[ToolRiskItem, ...]
    requires_acknowledgement: bool
    blocked_high_risk_tool_ids: tuple[UUID, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tools": [
                {**asdict(item), "id": str(item.id)}
                for item in self.tools
            ],
            "requires_acknowledgement": self.requires_acknowledgement,
            "blocked_high_risk_tool_ids": [
                str(value) for value in self.blocked_high_risk_tool_ids
            ],
            "risk_counts": {
                level: sum(1 for item in self.tools if item.risk_level == level)
                for level in ("low", "medium", "high")
            },
        }


class EvaluationPreflightService:
    async def inspect(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        targets: list[ResolvedEvaluationTarget],
        approved_high_risk_tool_ids: set[UUID] | None = None,
    ) -> EvaluationPreflight:
        approved = approved_high_risk_tool_ids or set()
        selected: dict[UUID, str] = {}
        snapshot_items: dict[UUID, ToolRiskItem] = {}

        for target in targets:
            if target.target_type == "agent":
                self._collect_runtime_config(
                    target.snapshot.get("runtime_config"),
                    selected=selected,
                    snapshot_items=snapshot_items,
                    source=f"agent:{target.display_version}",
                )
                continue

            bindings = target.snapshot.get("resolved_bindings")
            if not isinstance(bindings, dict):
                continue
            release_ids: list[UUID] = []
            for node_id, raw_binding in bindings.items():
                if not isinstance(raw_binding, dict):
                    continue
                self._collect_runtime_config(
                    (raw_binding.get("snapshot_override") or {}).get("runtime_config")
                    if isinstance(raw_binding.get("snapshot_override"), dict)
                    else None,
                    selected=selected,
                    snapshot_items=snapshot_items,
                    source=f"network-node:{node_id}",
                )
                raw_release_id = raw_binding.get("release_id")
                if raw_release_id:
                    try:
                        release_ids.append(UUID(str(raw_release_id)))
                    except (TypeError, ValueError):
                        continue
            if release_ids:
                releases = list(
                    (
                        await session.scalars(
                            select(AgentReleaseModel).where(
                                AgentReleaseModel.id.in_(release_ids),
                                AgentReleaseModel.project_id == project_id,
                            )
                        )
                    ).all()
                )
                for release in releases:
                    self._collect_runtime_config(
                        release.runtime_config,
                        selected=selected,
                        snapshot_items=snapshot_items,
                        source=f"network-release:{release.version}",
                    )

        live_ids = [tool_id for tool_id in selected if tool_id not in snapshot_items]
        live_items: dict[UUID, ToolRiskItem] = {}
        if live_ids:
            rows = list(
                (
                    await session.scalars(
                        select(AgentToolModel).where(
                            AgentToolModel.id.in_(live_ids),
                            AgentToolModel.project_id == project_id,
                            AgentToolModel.status == "active",
                        )
                    )
                ).all()
            )
            live_items = {
                row.id: ToolRiskItem(
                    id=row.id,
                    name=row.name,
                    risk_level=self._risk(row.risk_level),
                    source=selected.get(row.id, "live"),
                )
                for row in rows
            }

        items = {
            **live_items,
            **snapshot_items,
        }
        ordered = tuple(sorted(items.values(), key=lambda item: (item.risk_level, item.name)))
        blocked = tuple(
            item.id
            for item in ordered
            if item.risk_level == "high" and item.id not in approved
        )
        return EvaluationPreflight(
            tools=ordered,
            requires_acknowledgement=any(
                item.risk_level in {"medium", "high"} for item in ordered
            ),
            blocked_high_risk_tool_ids=blocked,
        )

    @staticmethod
    def enforce(
        preflight: EvaluationPreflight,
        *,
        acknowledge_tool_side_effects: bool,
    ) -> None:
        if preflight.blocked_high_risk_tool_ids:
            values = ", ".join(str(value) for value in preflight.blocked_high_risk_tool_ids)
            raise ConflictError(
                "Evaluation contains high-risk Tools without explicit approval: " + values
            )
        if preflight.requires_acknowledgement and not acknowledge_tool_side_effects:
            raise ConflictError(
                "Evaluation executes real Tools. Confirm Tool side effects before starting"
            )

    def _collect_runtime_config(
        self,
        runtime_config: Any,
        *,
        selected: dict[UUID, str],
        snapshot_items: dict[UUID, ToolRiskItem],
        source: str,
    ) -> None:
        if not isinstance(runtime_config, dict):
            return
        tools = runtime_config.get("tools")
        if not isinstance(tools, dict):
            return
        raw_ids = tools.get("tool_ids")
        if isinstance(raw_ids, list):
            for raw_id in raw_ids:
                try:
                    selected.setdefault(UUID(str(raw_id)), source)
                except (TypeError, ValueError):
                    continue
        snapshots = tools.get("snapshots")
        if not isinstance(snapshots, list):
            return
        for snapshot in snapshots:
            if not isinstance(snapshot, dict) or snapshot.get("id") is None:
                continue
            try:
                tool_id = UUID(str(snapshot["id"]))
            except (TypeError, ValueError):
                continue
            selected.setdefault(tool_id, source)
            snapshot_items[tool_id] = ToolRiskItem(
                id=tool_id,
                name=str(snapshot.get("name") or tool_id),
                risk_level=self._risk(snapshot.get("risk_level")),
                source=source,
            )

    @staticmethod
    def _risk(value: Any) -> str:
        normalized = str(value or "low").strip().lower()
        return normalized if normalized in {"low", "medium", "high"} else "high"


__all__ = [
    "EvaluationPreflight",
    "EvaluationPreflightService",
    "ToolRiskItem",
]
