from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from modules.network.application.service import NetworkApplicationService


def install_binding_concurrency_guards() -> None:
    """Bind promotion approvals to the exact mutable Agent Draft payload.

    Agent Draft is a singleton row whose ID remains stable while its payload is
    edited. Approval IDs therefore include a canonical snapshot hash. When a
    Draft changes between preview and confirmation, the locked promotion plan
    produces a different action ID and the transaction fails with 409 instead
    of promoting content the user did not review.
    """

    original = NetworkApplicationService._build_promotion_plan

    async def build_promotion_plan(
        self,
        session,
        definition,
        project_id: UUID,
        environment,
        *,
        lock: bool = False,
    ):
        plan = await original(
            self,
            session,
            definition,
            project_id,
            environment,
            lock=lock,
        )
        action_ids: dict[str, str] = {}
        for action in plan.get("actions", []):
            old_id = action["id"]
            release = await self._get_release(
                session,
                UUID(action["source_release_id"]),
                project_id,
                UUID(action["agent_id"]),
                lock=False,
            )
            if release is None:
                continue
            excluded = {
                "id",
                "created_at",
                "updated_at",
                "status",
                "promoted_by",
                "promoted_at",
            }
            snapshot_hash = self._snapshot_hash(
                {
                    column.name: deepcopy(getattr(release, column.name))
                    for column in release.__table__.columns
                    if column.name not in excluded
                }
            )
            new_id = f"{old_id}:{snapshot_hash}"
            action["id"] = new_id
            action["source_snapshot_hash"] = snapshot_hash
            action_ids[old_id] = new_id

        for node in plan.get("nodes", []):
            old_id = node.get("action_id")
            if old_id in action_ids:
                node["action_id"] = action_ids[old_id]
        return plan

    NetworkApplicationService._build_promotion_plan = build_promotion_plan
