from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from modules.evaluation.application.operational_catalog_service import (
    OperationalEvaluationCatalogService,
)


class CompleteEvaluationCatalogService(OperationalEvaluationCatalogService):
    """Final facade including safe lazy backfill of historical single-target Runs."""

    async def _backfill_single_runs(
        self,
        *,
        project_id: UUID,
        entity_id: UUID | None = None,
    ) -> None:
        conditions = [
            "r.project_id = :project_id",
            "r.evaluation_id IS NULL",
            "r.mode <> 'comparison'",
            "(SELECT count(*) FROM evaluation.targets t WHERE t.evaluation_run_id = r.id) = 1",
        ]
        params: dict[str, object] = {"project_id": project_id}
        if entity_id is not None:
            conditions.append(
                "EXISTS (SELECT 1 FROM evaluation.targets t "
                "WHERE t.evaluation_run_id = r.id AND t.entity_id = :entity_id)"
            )
            params["entity_id"] = entity_id
        async with self._session_factory() as session:
            rows = list(
                (
                    await session.execute(
                        text(
                            "SELECT r.id, r.requested_by FROM evaluation.runs r "
                            f"WHERE {' AND '.join(conditions)} "
                            "ORDER BY r.created_at ASC LIMIT 500"
                        ),
                        params,
                    )
                ).all()
            )
        for row in rows:
            try:
                await self.attach_run_to_evaluation(
                    project_id=project_id,
                    run_id=row.id,
                    created_by=row.requested_by,
                )
            except IntegrityError:
                # Concurrent catalog reads can race on the material identity.
                # The winning transaction created the Evaluation; retry resolves it.
                await self.attach_run_to_evaluation(
                    project_id=project_id,
                    run_id=row.id,
                    created_by=row.requested_by,
                )

    async def list_evaluations(self, *, project_id: UUID, entity_id=None, **kwargs):
        await self._backfill_single_runs(
            project_id=project_id,
            entity_id=entity_id,
        )
        return await super().list_evaluations(
            project_id=project_id,
            entity_id=entity_id,
            **kwargs,
        )


__all__ = ["CompleteEvaluationCatalogService"]
