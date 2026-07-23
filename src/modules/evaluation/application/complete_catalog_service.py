from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from modules.evaluation.application.evaluation_kpis import calculate_comparison_winner
from modules.evaluation.application.evaluation_protocol import (
    evaluation_protocol_hash,
    target_identity_hash,
)
from modules.evaluation.application.operational_catalog_service import (
    OperationalEvaluationCatalogService,
)
from modules.evaluation.application.run_judge import (
    judge_summary_from_run,
    run_judge_protocol,
)
from modules.evaluation.application.target_resolver import EvaluationTargetResolver
from modules.evaluation.infra.database.catalog_models import (
    EvaluationComparisonModel,
    EvaluationModel,
)
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationSuiteModel,
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
)
from shared.infra.errors import ConflictError, NotFoundError, ValidationError


class CompleteEvaluationCatalogService(OperationalEvaluationCatalogService):
    """Final catalog facade with protocol identity, freshness and KPI winners."""

    @staticmethod
    def _run_summary(run) -> dict[str, Any] | None:
        payload = OperationalEvaluationCatalogService._run_summary(run)
        if payload is not None:
            payload["judge"] = judge_summary_from_run(run)
            aggregate = run.aggregate_result if isinstance(run.aggregate_result, dict) else {}
            payload["kpis"] = aggregate.get("kpis") if isinstance(aggregate.get("kpis"), dict) else None
        return payload

    @staticmethod
    def _material_protocol_hash(
        suite: EvaluationSuiteVersionModel,
        run: EvaluationRunModel,
    ) -> str:
        protocol = run_judge_protocol(run)
        if protocol.get("source") != "run_override":
            return evaluation_protocol_hash(suite)
        return evaluation_protocol_hash(
            suite,
            judge_provider_model_id=protocol.get("judge_provider_model_id"),
            judge_config=(
                protocol.get("normalized_judge_config")
                if isinstance(protocol.get("normalized_judge_config"), dict)
                else None
            ),
            judge_model_snapshot_hash=protocol.get("judge_model_snapshot_hash"),
        )

    async def preview_evaluation(
        self,
        *,
        project_id: UUID,
        suite_version_id: UUID,
        repetitions: int,
        target: dict[str, Any],
        acknowledge_tool_side_effects: bool = False,
        approved_high_risk_tool_ids: list[UUID] | None = None,
        judge_provider_model_id: UUID | None = None,
    ) -> dict[str, Any]:
        payload = await self._runs.preview_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            candidate=target,
            baseline=None,
            acknowledge_tool_side_effects=acknowledge_tool_side_effects,
            approved_high_risk_tool_ids=approved_high_risk_tool_ids or [],
            judge_provider_model_id=judge_provider_model_id,
        )
        async with self._session_factory() as session:
            suite = await session.get(EvaluationSuiteVersionModel, suite_version_id)
            if suite is None or suite.project_id != project_id:
                raise NotFoundError("Evaluation Suite version not found")
            if payload.get("judge_override"):
                judge_preflight = payload.get("judge_preflight")
                judge_preflight = (
                    judge_preflight if isinstance(judge_preflight, dict) else {}
                )
                judge_model = judge_preflight.get("judge_model")
                judge_model = judge_model if isinstance(judge_model, dict) else {}
                protocol_hash = evaluation_protocol_hash(
                    suite,
                    judge_provider_model_id=payload.get("judge_provider_model_id"),
                    judge_config=(
                        judge_preflight.get("normalized_judge_config")
                        if isinstance(
                            judge_preflight.get("normalized_judge_config"), dict
                        )
                        else None
                    ),
                    judge_model_snapshot_hash=judge_model.get("snapshot_hash"),
                )
            else:
                protocol_hash = evaluation_protocol_hash(suite)
        return {
            **payload,
            "mode": "single_snapshot",
            "target": payload.get("candidate"),
            "candidate": None,
            "baseline": None,
            "evaluation_protocol_hash": protocol_hash,
            "operations": {"evaluation_runs": 1, "comparisons": 0},
        }

    async def create_evaluation_run(
        self,
        *,
        project_id: UUID,
        suite_version_id: UUID,
        repetitions: int,
        target: dict[str, Any],
        requested_by: UUID | None,
        acknowledge_tool_side_effects: bool = False,
        approved_high_risk_tool_ids: list[UUID] | None = None,
        idempotency_key: str | None = None,
        judge_provider_model_id: UUID | None = None,
    ) -> dict[str, Any]:
        run_payload = await self._runs.create_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            candidate=target,
            baseline=None,
            requested_by=requested_by,
            acknowledge_tool_side_effects=acknowledge_tool_side_effects,
            approved_high_risk_tool_ids=approved_high_risk_tool_ids or [],
            idempotency_key=idempotency_key,
            judge_provider_model_id=judge_provider_model_id,
        )
        evaluation = await self.attach_run_to_evaluation(
            project_id=project_id,
            run_id=UUID(str(run_payload["id"])),
            created_by=requested_by,
        )
        return {
            **run_payload,
            "evaluation_id": evaluation["id"],
            "evaluation_protocol_hash": evaluation["evaluation_protocol_hash"],
        }

    async def attach_run_to_evaluation(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        created_by: UUID | None,
    ) -> dict[str, Any]:
        """Attach by target + immutable Suite + effective Judge protocol."""

        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None or run.project_id != project_id:
                raise NotFoundError("Evaluation Run not found")
            targets = list(
                (
                    await session.scalars(
                        select(EvaluationTargetModel).where(
                            EvaluationTargetModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            if len(targets) != 1:
                raise ConflictError(
                    "Only single-target Runs can be attached to the Evaluation catalog"
                )
            target = targets[0]
            suite = await session.get(EvaluationSuiteVersionModel, run.suite_version_id)
            if suite is None or suite.project_id != project_id:
                raise NotFoundError("Evaluation Suite version not found")
            protocol_hash = self._material_protocol_hash(suite, run)
            identity_hash = target_identity_hash(
                target_type=target.target_type,
                entity_id=target.entity_id,
                source_type=target.source_type,
                target_version_id=target.agent_release_id or target.network_version_id,
                snapshot_hash=target.snapshot_hash,
            )
            evaluation = await session.scalar(
                select(EvaluationModel).where(
                    EvaluationModel.project_id == project_id,
                    EvaluationModel.suite_version_id == run.suite_version_id,
                    EvaluationModel.target_identity_hash == identity_hash,
                    EvaluationModel.evaluation_protocol_hash == protocol_hash,
                )
            )
            if evaluation is None:
                evaluation = EvaluationModel(
                    project_id=project_id,
                    suite_version_id=run.suite_version_id,
                    evaluation_protocol_hash=protocol_hash,
                    target_type=target.target_type,
                    entity_id=target.entity_id,
                    source_type=target.source_type,
                    target_version_id=target.agent_release_id or target.network_version_id,
                    target_snapshot_hash=target.snapshot_hash,
                    target_identity_hash=identity_hash,
                    display_name=target.display_name,
                    display_version=target.display_version,
                    status="active",
                    latest_run_id=run.id,
                    created_by=created_by,
                )
                session.add(evaluation)
                await session.flush()
            else:
                evaluation.latest_run_id = run.id
                evaluation.display_name = target.display_name
                evaluation.display_version = target.display_version
            await session.execute(
                text(
                    "UPDATE evaluation.runs "
                    "SET evaluation_id = :evaluation_id, evaluation_protocol_hash = :protocol_hash "
                    "WHERE id = :run_id AND project_id = :project_id"
                ),
                {
                    "evaluation_id": evaluation.id,
                    "protocol_hash": protocol_hash,
                    "run_id": run.id,
                    "project_id": project_id,
                },
            )
            return self._evaluation_payload(
                evaluation,
                run_count=None,
                protocol_hash=protocol_hash,
            )

    async def create_paired_comparison(
        self,
        *,
        project_id: UUID,
        suite_version_id: UUID,
        repetitions: int,
        candidate: dict[str, Any],
        reference: dict[str, Any],
        requested_by: UUID | None,
        acknowledge_tool_side_effects: bool,
        approved_high_risk_tool_ids: list[UUID],
        idempotency_key: str,
        judge_provider_model_id: UUID | None = None,
    ) -> dict[str, Any]:
        if not idempotency_key or len(idempotency_key.strip()) < 8:
            raise ValidationError("Paired Comparison requires an idempotency key")
        candidate_run = await self.create_evaluation_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            target=candidate,
            requested_by=requested_by,
            acknowledge_tool_side_effects=acknowledge_tool_side_effects,
            approved_high_risk_tool_ids=approved_high_risk_tool_ids,
            idempotency_key=f"{idempotency_key}:candidate",
            judge_provider_model_id=judge_provider_model_id,
        )
        reference_run = await self.create_evaluation_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            target=reference,
            requested_by=requested_by,
            acknowledge_tool_side_effects=acknowledge_tool_side_effects,
            approved_high_risk_tool_ids=approved_high_risk_tool_ids,
            idempotency_key=f"{idempotency_key}:reference",
            judge_provider_model_id=judge_provider_model_id,
        )
        comparison = await self.create_comparison_from_runs(
            project_id=project_id,
            candidate_run_id=UUID(str(candidate_run["id"])),
            reference_run_id=UUID(str(reference_run["id"])),
            candidate_revision=1,
            reference_revision=1,
            requested_by=requested_by,
            idempotency_key=idempotency_key,
        )
        comparison["created_runs"] = {
            "candidate": candidate_run,
            "reference": reference_run,
        }
        return comparison

    async def _refresh_comparison(
        self,
        session,
        comparison: EvaluationComparisonModel,
    ) -> None:
        await super()._refresh_comparison(session, comparison)
        aggregate = (
            dict(comparison.aggregate_result)
            if isinstance(comparison.aggregate_result, dict)
            else {}
        )
        candidate_side = aggregate.get("candidate")
        reference_side = aggregate.get("reference")
        if not isinstance(candidate_side, dict) or not isinstance(reference_side, dict):
            return
        candidate_run = await session.get(EvaluationRunModel, comparison.candidate_run_id)
        reference_run = await session.get(EvaluationRunModel, comparison.reference_run_id)
        suite = await session.get(EvaluationSuiteVersionModel, comparison.suite_version_id)
        if candidate_run is None or reference_run is None or suite is None:
            return

        candidate_aggregate = (
            candidate_run.aggregate_result
            if isinstance(candidate_run.aggregate_result, dict)
            else {}
        )
        reference_aggregate = (
            reference_run.aggregate_result
            if isinstance(reference_run.aggregate_result, dict)
            else {}
        )
        candidate_kpis = candidate_aggregate.get("kpis")
        reference_kpis = reference_aggregate.get("kpis")
        candidate_kpis = dict(candidate_kpis) if isinstance(candidate_kpis, dict) else self._legacy_kpis(candidate_side, candidate_run)
        reference_kpis = dict(reference_kpis) if isinstance(reference_kpis, dict) else self._legacy_kpis(reference_side, reference_run)
        candidate_side["kpis"] = candidate_kpis
        reference_side["kpis"] = reference_kpis
        aggregate["candidate"] = candidate_side
        aggregate["reference"] = reference_side
        aggregate["winner"] = calculate_comparison_winner(
            candidate_kpis,
            reference_kpis,
            acceptance_policy=suite.acceptance_policy,
            authoritative=(
                comparison.status == "ready"
                and candidate_run.repetitions == reference_run.repetitions
            ),
        )
        comparison.aggregate_result = aggregate

    @staticmethod
    def _legacy_kpis(side: dict[str, Any], run: EvaluationRunModel) -> dict[str, Any]:
        summary = side.get("summary") if isinstance(side.get("summary"), dict) else {}
        runtime = side.get("runtime") if isinstance(side.get("runtime"), dict) else {}
        return {
            "schema_version": "evaluation-kpis-legacy-fallback",
            "quality_score": summary.get("weighted_score", run.overall_score),
            "pass_rate": summary.get("weighted_pass_rate", run.pass_rate),
            "runtime_cost_usd_per_trial": runtime.get("runtime_cost_usd"),
            "latency_median_ms": runtime.get("latency_median_ms"),
        }

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
        suites_by_id = {suite.id: suite for suite in suites}
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

    async def _with_freshness(
        self,
        *,
        project_id: UUID,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        resolver = EvaluationTargetResolver(self._session_factory)
        result: list[dict[str, Any]] = []
        async with self._session_factory() as session:
            for item in items:
                source_type = str(item.get("source_type") or "")
                if source_type == "release":
                    freshness = {
                        "status": "immutable",
                        "evaluated_snapshot_hash": item.get("target_snapshot_hash"),
                        "current_snapshot_hash": item.get("target_snapshot_hash"),
                    }
                elif source_type not in {"draft", "staging"}:
                    freshness = {
                        "status": "unknown",
                        "evaluated_snapshot_hash": item.get("target_snapshot_hash"),
                        "current_snapshot_hash": None,
                    }
                else:
                    try:
                        current = await resolver.resolve(
                            session,
                            project_id=project_id,
                            target_type=str(item.get("target_type")),
                            source_type=source_type,
                            entity_id=UUID(str(item.get("entity_id"))),
                            version_id=None,
                        )
                        freshness = {
                            "status": (
                                "current"
                                if current.snapshot_hash == item.get("target_snapshot_hash")
                                else "superseded"
                            ),
                            "evaluated_snapshot_hash": item.get("target_snapshot_hash"),
                            "current_snapshot_hash": current.snapshot_hash,
                            "current_display_version": current.display_version,
                        }
                    except Exception:
                        freshness = {
                            "status": "target_unavailable",
                            "evaluated_snapshot_hash": item.get("target_snapshot_hash"),
                            "current_snapshot_hash": None,
                        }
                result.append({**item, "freshness": freshness})
        return result

    async def list_evaluations(
        self,
        *,
        project_id: UUID,
        entity_id: UUID | None = None,
        target_version_id: UUID | None = None,
        source_type: str | None = None,
        **kwargs,
    ) -> list[dict[str, Any]]:
        await self._backfill_single_runs(project_id=project_id, entity_id=entity_id)
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
        items = await self._enrich_suite_metadata(project_id=project_id, items=items)
        return await self._with_freshness(project_id=project_id, items=items)

    async def get_evaluation(self, *, project_id: UUID, evaluation_id: UUID):
        item = await super().get_evaluation(
            project_id=project_id,
            evaluation_id=evaluation_id,
        )
        enriched = await self._enrich_suite_metadata(
            project_id=project_id,
            items=[item],
        )
        fresh = await self._with_freshness(project_id=project_id, items=enriched)
        return fresh[0]


__all__ = ["CompleteEvaluationCatalogService"]
