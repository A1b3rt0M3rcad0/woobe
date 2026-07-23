from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from modules.evaluation.application.operational_catalog_service import (
    OperationalEvaluationCatalogService,
)
from modules.evaluation.infra.database.models import (
    EvaluationSuiteModel,
    EvaluationSuiteVersionModel,
)


class CompleteEvaluationCatalogService(OperationalEvaluationCatalogService):
    """Final facade including safe lazy backfill and operational catalog labels."""

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
                # Concurrent catalog reads can race on the material identity. The
                # winner created the Evaluation; a second attach resolves the row.
                await self.attach_run_to_evaluation(
                    project_id=project_id,
                    run_id=row.id,
                    created_by=row.requested_by,
                )

    async def _enrich_suite_metadata(
        self,
        *,
        project_id: UUID,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        version_ids = {
            UUID(str(item["suite_version_id"]))
            for item in items
            if item.get("suite_version_id")
        }
        if not version_ids:
            return items
        async with self._session_factory() as session:
            versions = list(
                (
                    await session.scalars(
                        select(EvaluationSuiteVersionModel).where(
                            EvaluationSuiteVersionModel.project_id == project_id,
                            EvaluationSuiteVersionModel.id.in_(version_ids),
                        )
                    )
                ).all()
            )
            suite_ids = {version.suite_id for version in versions}
            suites = list(
                (
                    await session.scalars(
                        select(EvaluationSuiteModel).where(
                            EvaluationSuiteModel.project_id == project_id,
                            EvaluationSuiteModel.id.in_(suite_ids),
                        )
                    )
                ).all()
            )
        versions_by_id = {str(version.id): version for version in versions}
        suites_by_id = {version.id: version for version in suites}
        enriched: list[dict[str, Any]] = []
        for item in items:
            version = versions_by_id.get(str(item.get("suite_version_id")))
            suite = suites_by_id.get(version.suite_id) if version is not None else None
            enriched.append(
                {
                    **item,
                    "suite_id": str(suite.id) if suite is not None else None,
                    "suite_name": suite.name if suite is not None else None,
                    "suite_version": version.version if version is not None else None,
                    "dataset_version_id": (
                        str(version.dataset_version_id) if version is not None else None
                    ),
                    "judge_provider_model_id": (
                        str(version.judge_provider_model_id) if version is not None else None
                    ),
                }
            )
        return enriched

    async def list_evaluations(
        self,
        *,
        project_id: UUID,
        entity_id: UUID | None = None,
        target_version_id: UUID | None = None,
        source_type: str | None = None,
        **kwargs,
    ) -> list[dict[str, Any]]:
        await self._backfill_single_runs(
            project_id=project_id,
            entity_id=entity_id,
        )
        items = await super().list_evaluations(
            project_id=project_id,
            entity_id=entity_id,
            **kwargs,
        )
        if target_version_id is not None:
            items = [
                item
                for item in items
                if str(item.get("target_version_id") or "") == str(target_version_id)
            ]
        if source_type is not None:
            items = [
                item for item in items if str(item.get("source_type") or "") == source_type
            ]
        return await self._enrich_suite_metadata(project_id=project_id, items=items)

    async def get_evaluation(self, *, project_id: UUID, evaluation_id: UUID):
        item = await super().get_evaluation(
            project_id=project_id,
            evaluation_id=evaluation_id,
        )
        enriched = await self._enrich_suite_metadata(
            project_id=project_id,
            items=[item],
        )
        return enriched[0]


__all__ = ["CompleteEvaluationCatalogService"]
