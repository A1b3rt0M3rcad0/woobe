from __future__ import annotations

import random
from dataclasses import asdict
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.evaluation.application.target_resolver import EvaluationTargetResolver
from modules.evaluation.domain.enums import EvaluationMode, EvaluationRunStatus
from modules.evaluation.infra.database.models import (
    EstimateRunModel,
    EvaluationCheckResultModel,
    EvaluationDatasetModel,
    EvaluationDatasetVersionModel,
    EvaluationRunModel,
    EvaluationSuiteModel,
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
    EvaluatorModelCallModel,
    ReleaseQualificationModel,
)
from modules.evaluation.infra.judge import canonical_hash
from shared.infra.errors import ConflictError, NotFoundError, ValidationError


class EvaluationApplicationService:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory
        self._target_resolver = EvaluationTargetResolver(session_factory)

    async def create_dataset(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str,
        cases: list[dict[str, Any]],
        change_description: str | None,
        created_by: UUID | None,
    ) -> dict[str, Any]:
        if not cases:
            raise ValidationError("Evaluation Dataset requires at least one Test Case")
        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(EvaluationDatasetModel).where(
                    EvaluationDatasetModel.project_id == project_id,
                    func.lower(func.btrim(EvaluationDatasetModel.name))
                    == name.strip().lower(),
                )
            )
            if existing is not None:
                raise ConflictError("An Evaluation Dataset with this name already exists")
            dataset = EvaluationDatasetModel(
                project_id=project_id,
                name=name.strip(),
                description=description.strip(),
                status="active",
                created_by=created_by,
            )
            session.add(dataset)
            await session.flush()
            version = await self._create_dataset_version(
                session,
                dataset=dataset,
                project_id=project_id,
                cases=cases,
                change_description=change_description,
                created_by=created_by,
            )
            dataset.current_version_id = version.id
            await session.flush()
            return self._dataset_payload(dataset, version, len(cases))

    async def create_dataset_version(
        self,
        *,
        project_id: UUID,
        dataset_id: UUID,
        cases: list[dict[str, Any]],
        change_description: str | None,
        created_by: UUID | None,
    ) -> dict[str, Any]:
        if not cases:
            raise ValidationError("Evaluation Dataset version requires Test Cases")
        async with self._session_factory() as session, session.begin():
            dataset = await session.get(EvaluationDatasetModel, dataset_id, with_for_update=True)
            if dataset is None or dataset.project_id != project_id:
                raise NotFoundError("Evaluation Dataset not found")
            version = await self._create_dataset_version(
                session,
                dataset=dataset,
                project_id=project_id,
                cases=cases,
                change_description=change_description,
                created_by=created_by,
            )
            dataset.current_version_id = version.id
            await session.flush()
            return self._dataset_payload(dataset, version, len(cases))

    async def _create_dataset_version(
        self,
        session,
        *,
        dataset: EvaluationDatasetModel,
        project_id: UUID,
        cases: list[dict[str, Any]],
        change_description: str | None,
        created_by: UUID | None,
    ) -> EvaluationDatasetVersionModel:
        version_count = await session.scalar(
            select(func.count(EvaluationDatasetVersionModel.id)).where(
                EvaluationDatasetVersionModel.dataset_id == dataset.id
            )
        )
        version = EvaluationDatasetVersionModel(
            dataset_id=dataset.id,
            project_id=project_id,
            version=f"v{int(version_count or 0) + 1}",
            content_hash=canonical_hash(cases),
            change_description=change_description,
            created_by=created_by,
        )
        session.add(version)
        await session.flush()
        rows: list[EvaluationTestCaseModel] = []
        for index, raw in enumerate(cases, start=1):
            input_payload = raw.get("input_payload")
            if not isinstance(input_payload, dict):
                message = raw.get("message")
                input_payload = {"message": message} if isinstance(message, str) else {}
            if not input_payload.get("message") and not input_payload.get("input") and not input_payload.get("prompt"):
                raise ValidationError(f"Test Case {index} requires a message input")
            rows.append(
                EvaluationTestCaseModel(
                    dataset_version_id=version.id,
                    project_id=project_id,
                    position=index,
                    name=str(raw.get("name") or f"Case {index}").strip(),
                    input_payload=input_payload,
                    initial_context=raw.get("initial_context") if isinstance(raw.get("initial_context"), dict) else None,
                    expected_contract=raw.get("expected_contract") if isinstance(raw.get("expected_contract"), dict) else {},
                    severity=str(raw.get("severity") or "normal"),
                    weight=float(raw.get("weight") or 1.0),
                    blocking=bool(raw.get("blocking", False)),
                    tags=[str(item) for item in raw.get("tags", [])],
                    production_frequency=(
                        float(raw["production_frequency"])
                        if raw.get("production_frequency") is not None
                        else None
                    ),
                )
            )
        session.add_all(rows)
        return version

    async def list_datasets(self, project_id: UUID) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            datasets = list(
                (
                    await session.scalars(
                        select(EvaluationDatasetModel)
                        .where(
                            EvaluationDatasetModel.project_id == project_id,
                            EvaluationDatasetModel.status != "archived",
                        )
                        .order_by(EvaluationDatasetModel.updated_at.desc())
                    )
                ).all()
            )
            result: list[dict[str, Any]] = []
            for dataset in datasets:
                version = (
                    await session.get(
                        EvaluationDatasetVersionModel,
                        dataset.current_version_id,
                    )
                    if dataset.current_version_id
                    else None
                )
                case_count = 0
                if version is not None:
                    case_count = int(
                        await session.scalar(
                            select(func.count(EvaluationTestCaseModel.id)).where(
                                EvaluationTestCaseModel.dataset_version_id == version.id
                            )
                        )
                        or 0
                    )
                result.append(self._dataset_payload(dataset, version, case_count))
            return result

    async def get_dataset(self, project_id: UUID, dataset_id: UUID) -> dict[str, Any]:
        async with self._session_factory() as session:
            dataset = await session.get(EvaluationDatasetModel, dataset_id)
            if dataset is None or dataset.project_id != project_id:
                raise NotFoundError("Evaluation Dataset not found")
            versions = list(
                (
                    await session.scalars(
                        select(EvaluationDatasetVersionModel)
                        .where(EvaluationDatasetVersionModel.dataset_id == dataset.id)
                        .order_by(EvaluationDatasetVersionModel.created_at.desc())
                    )
                ).all()
            )
            current = next((item for item in versions if item.id == dataset.current_version_id), None)
            cases = []
            if current is not None:
                cases = [
                    self._case_payload(item)
                    for item in (
                        await session.scalars(
                            select(EvaluationTestCaseModel)
                            .where(EvaluationTestCaseModel.dataset_version_id == current.id)
                            .order_by(EvaluationTestCaseModel.position)
                        )
                    ).all()
                ]
            return {
                **self._dataset_payload(dataset, current, len(cases)),
                "versions": [
                    {
                        "id": str(item.id),
                        "version": item.version,
                        "content_hash": item.content_hash,
                        "change_description": item.change_description,
                        "created_at": item.created_at,
                    }
                    for item in versions
                ],
                "cases": cases,
            }

    async def create_suite(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str,
        target_type: str,
        dataset_version_id: UUID,
        judge_provider_model_id: UUID,
        judge_config: dict[str, Any],
        rubric: dict[str, Any],
        deterministic_checks: dict[str, Any],
        acceptance_policy: dict[str, Any],
        repetition_policy: dict[str, Any],
        estimate_defaults: dict[str, Any],
        created_by: UUID | None,
    ) -> dict[str, Any]:
        if target_type not in {"agent", "network"}:
            raise ValidationError("Evaluation Suite target_type must be agent or network")
        async with self._session_factory() as session, session.begin():
            dataset_version = await session.get(
                EvaluationDatasetVersionModel,
                dataset_version_id,
            )
            if dataset_version is None or dataset_version.project_id != project_id:
                raise NotFoundError("Evaluation Dataset version not found")
            provider_model = await session.get(ProviderModelModel, judge_provider_model_id)
            if (
                provider_model is None
                or provider_model.project_id != project_id
                or provider_model.status != "active"
            ):
                raise NotFoundError("Evaluator Provider Model not found")
            existing = await session.scalar(
                select(EvaluationSuiteModel).where(
                    EvaluationSuiteModel.project_id == project_id,
                    func.lower(func.btrim(EvaluationSuiteModel.name))
                    == name.strip().lower(),
                )
            )
            if existing is not None:
                raise ConflictError("An Evaluation Suite with this name already exists")
            suite = EvaluationSuiteModel(
                project_id=project_id,
                name=name.strip(),
                description=description.strip(),
                target_type=target_type,
                status="active",
                created_by=created_by,
            )
            session.add(suite)
            await session.flush()
            version = EvaluationSuiteVersionModel(
                suite_id=suite.id,
                project_id=project_id,
                version="v1",
                dataset_version_id=dataset_version_id,
                judge_provider_model_id=judge_provider_model_id,
                judge_config=judge_config,
                rubric=rubric,
                deterministic_checks=deterministic_checks,
                acceptance_policy=acceptance_policy,
                repetition_policy=repetition_policy,
                estimate_defaults=estimate_defaults,
                suite_hash=canonical_hash(
                    {
                        "dataset_version_id": dataset_version_id,
                        "judge_provider_model_id": judge_provider_model_id,
                        "judge_config": judge_config,
                        "rubric": rubric,
                        "deterministic_checks": deterministic_checks,
                        "acceptance_policy": acceptance_policy,
                        "repetition_policy": repetition_policy,
                        "estimate_defaults": estimate_defaults,
                    }
                ),
                created_by=created_by,
            )
            session.add(version)
            await session.flush()
            suite.current_version_id = version.id
            return self._suite_payload(suite, version)

    async def list_suites(self, project_id: UUID) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            suites = list(
                (
                    await session.scalars(
                        select(EvaluationSuiteModel)
                        .where(
                            EvaluationSuiteModel.project_id == project_id,
                            EvaluationSuiteModel.status != "archived",
                        )
                        .order_by(EvaluationSuiteModel.updated_at.desc())
                    )
                ).all()
            )
            result = []
            for suite in suites:
                version = (
                    await session.get(
                        EvaluationSuiteVersionModel,
                        suite.current_version_id,
                    )
                    if suite.current_version_id
                    else None
                )
                result.append(self._suite_payload(suite, version))
            return result

    async def preview_run(
        self,
        *,
        project_id: UUID,
        suite_version_id: UUID,
        repetitions: int,
        candidate: dict[str, Any],
        baseline: dict[str, Any] | None,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            suite = await session.get(EvaluationSuiteVersionModel, suite_version_id)
            if suite is None or suite.project_id != project_id:
                raise NotFoundError("Evaluation Suite version not found")
            suite_root = await session.get(EvaluationSuiteModel, suite.suite_id)
            if suite_root is None:
                raise NotFoundError("Evaluation Suite not found")
            candidate_target = await self._resolve_target_dict(
                session,
                project_id=project_id,
                raw=candidate,
            )
            baseline_target = (
                await self._resolve_target_dict(session, project_id=project_id, raw=baseline)
                if baseline
                else None
            )
            if candidate_target.target_type != suite_root.target_type:
                raise ValidationError("Candidate target type does not match the Evaluation Suite")
            if baseline_target and baseline_target.target_type != candidate_target.target_type:
                raise ValidationError("Candidate and Baseline must use the same target type")
            case_count = int(
                await session.scalar(
                    select(func.count(EvaluationTestCaseModel.id)).where(
                        EvaluationTestCaseModel.dataset_version_id
                        == suite.dataset_version_id
                    )
                )
                or 0
            )
            target_count = 2 if baseline_target else 1
            return {
                "mode": "comparison" if baseline_target else "absolute",
                "candidate": asdict(candidate_target),
                "baseline": asdict(baseline_target) if baseline_target else None,
                "case_count": case_count,
                "repetitions": repetitions,
                "target_run_count": case_count * repetitions * target_count,
                "judge_call_count": case_count * repetitions * target_count,
                "judge_provider_model_id": str(suite.judge_provider_model_id),
                "tool_execution_warning": "Evaluation Runs execute the selected target's real Tools. Review side effects before starting.",
            }

    async def create_run(
        self,
        *,
        project_id: UUID,
        suite_version_id: UUID,
        repetitions: int,
        candidate: dict[str, Any],
        baseline: dict[str, Any] | None,
        requested_by: UUID | None,
    ) -> dict[str, Any]:
        if repetitions < 1 or repetitions > 25:
            raise ValidationError("Evaluation repetitions must be between 1 and 25")
        async with self._session_factory() as session, session.begin():
            suite = await session.get(EvaluationSuiteVersionModel, suite_version_id)
            if suite is None or suite.project_id != project_id:
                raise NotFoundError("Evaluation Suite version not found")
            suite_root = await session.get(EvaluationSuiteModel, suite.suite_id)
            if suite_root is None:
                raise NotFoundError("Evaluation Suite not found")
            candidate_target = await self._resolve_target_dict(
                session,
                project_id=project_id,
                raw=candidate,
            )
            baseline_target = (
                await self._resolve_target_dict(session, project_id=project_id, raw=baseline)
                if baseline
                else None
            )
            if candidate_target.target_type != suite_root.target_type:
                raise ValidationError("Candidate target type does not match the Evaluation Suite")
            if baseline_target and baseline_target.target_type != candidate_target.target_type:
                raise ValidationError("Candidate and Baseline must use the same target type")
            run = EvaluationRunModel(
                project_id=project_id,
                suite_version_id=suite_version_id,
                mode=(
                    EvaluationMode.COMPARISON.value
                    if baseline_target
                    else EvaluationMode.ABSOLUTE.value
                ),
                status=EvaluationRunStatus.QUEUED.value,
                repetitions=repetitions,
                execution_order="paired_interleaved",
                randomization_seed=random.SystemRandom().randint(1, 2_147_483_647),
                requested_by=requested_by,
            )
            session.add(run)
            await session.flush()
            candidate_model = EvaluationTargetModel(
                evaluation_run_id=run.id,
                project_id=project_id,
                side="candidate" if baseline_target else "single",
                **asdict(candidate_target),
            )
            session.add(candidate_model)
            baseline_model = None
            if baseline_target:
                baseline_model = EvaluationTargetModel(
                    evaluation_run_id=run.id,
                    project_id=project_id,
                    side="baseline",
                    **asdict(baseline_target),
                )
                session.add(baseline_model)
            await session.flush()
            run.candidate_target_id = candidate_model.id
            run.baseline_target_id = baseline_model.id if baseline_model else None
            await session.flush()
            return self._run_payload(run, [candidate_model, *([baseline_model] if baseline_model else [])])

    async def list_runs(self, project_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            runs = list(
                (
                    await session.scalars(
                        select(EvaluationRunModel)
                        .where(EvaluationRunModel.project_id == project_id)
                        .order_by(EvaluationRunModel.created_at.desc())
                        .limit(min(max(limit, 1), 200))
                    )
                ).all()
            )
            result = []
            for run in runs:
                targets = list(
                    (
                        await session.scalars(
                            select(EvaluationTargetModel).where(
                                EvaluationTargetModel.evaluation_run_id == run.id
                            )
                        )
                    ).all()
                )
                result.append(self._run_payload(run, targets))
            return result

    async def get_run(self, project_id: UUID, run_id: UUID) -> dict[str, Any]:
        async with self._session_factory() as session:
            run = await session.get(EvaluationRunModel, run_id)
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
            trials = list(
                (
                    await session.scalars(
                        select(EvaluationTrialModel)
                        .where(EvaluationTrialModel.evaluation_run_id == run.id)
                        .order_by(EvaluationTrialModel.execution_order)
                    )
                ).all()
            )
            cases = {
                item.id: item
                for item in (
                    await session.scalars(
                        select(EvaluationTestCaseModel).where(
                            EvaluationTestCaseModel.id.in_(
                                [trial.test_case_id for trial in trials] or [UUID(int=0)]
                            )
                        )
                    )
                ).all()
            }
            target_index = {item.id: item for item in targets}
            model_calls = list(
                (
                    await session.scalars(
                        select(EvaluatorModelCallModel).where(
                            EvaluatorModelCallModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            checks = list(
                (
                    await session.scalars(
                        select(EvaluationCheckResultModel).where(
                            EvaluationCheckResultModel.evaluation_trial_id.in_(
                                [trial.id for trial in trials] or [UUID(int=0)]
                            )
                        )
                    )
                ).all()
            )
            checks_by_trial: dict[UUID, list[dict[str, Any]]] = {}
            for item in checks:
                checks_by_trial.setdefault(item.evaluation_trial_id, []).append(
                    {
                        "id": str(item.id),
                        "evaluator_key": item.evaluator_key,
                        "evaluator_type": item.evaluator_type,
                        "dimension": item.dimension,
                        "status": item.status,
                        "score": item.score,
                        "blocking": item.blocking,
                        "reason": item.reason,
                        "evidence": item.evidence,
                    }
                )
            estimates = list(
                (
                    await session.scalars(
                        select(EstimateRunModel).where(
                            EstimateRunModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            payload = self._run_payload(run, targets)
            payload["trials"] = [
                {
                    "id": str(item.id),
                    "target_id": str(item.evaluation_target_id),
                    "side": target_index[item.evaluation_target_id].side
                    if item.evaluation_target_id in target_index
                    else None,
                    "case": self._case_payload(cases[item.test_case_id])
                    if item.test_case_id in cases
                    else None,
                    "repetition": item.repetition,
                    "pair_key": item.pair_key,
                    "status": item.status,
                    "score": item.score,
                    "passed": item.passed,
                    "agent_run_id": str(item.agent_run_id) if item.agent_run_id else None,
                    "network_execution_id": str(item.network_execution_id)
                    if item.network_execution_id
                    else None,
                    "trace_id": str(item.root_trace_id) if item.root_trace_id else None,
                    "output": item.output_payload,
                    "metrics": item.metrics,
                    "failure_code": item.failure_code,
                    "failure_detail": item.failure_detail,
                    "checks": checks_by_trial.get(item.id, []),
                }
                for item in trials
            ]
            payload["judge_calls"] = [
                {
                    "id": str(item.id),
                    "trial_id": str(item.evaluation_trial_id),
                    "provider_model_id": str(item.provider_model_id),
                    "provider": item.provider,
                    "model": item.model,
                    "status": item.status,
                    "cost_usd": float(item.cost_usd) if item.cost_usd is not None else None,
                    "cost_status": item.cost_status,
                    "latency_ms": item.latency_ms,
                    "structured_result": item.structured_result,
                    "error": item.error,
                }
                for item in model_calls
            ]
            payload["estimates"] = [
                {
                    "id": str(item.id),
                    "target_id": str(item.target_id),
                    "volume": item.volume,
                    "volume_unit": item.volume_unit,
                    "confidence": item.confidence,
                    "observation_summary": item.observation_summary,
                    "scenarios": item.scenarios,
                    "limitations": item.limitations,
                }
                for item in estimates
            ]
            return payload

    async def cancel_run(self, project_id: UUID, run_id: UUID) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None or run.project_id != project_id:
                raise NotFoundError("Evaluation Run not found")
            if run.status in {
                EvaluationRunStatus.COMPLETED.value,
                EvaluationRunStatus.PARTIALLY_COMPLETED.value,
                EvaluationRunStatus.FAILED.value,
                EvaluationRunStatus.CANCELLED.value,
            }:
                return self._run_payload(run, [])
            from datetime import datetime, timezone

            run.cancel_requested_at = datetime.now(timezone.utc)
            run.status = EvaluationRunStatus.CANCEL_REQUESTED.value
            return self._run_payload(run, [])

    async def list_qualifications(
        self,
        *,
        project_id: UUID,
        target_type: str | None = None,
        entity_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            statement = select(ReleaseQualificationModel).where(
                ReleaseQualificationModel.project_id == project_id
            )
            if target_type:
                statement = statement.where(
                    ReleaseQualificationModel.target_type == target_type
                )
            if entity_id:
                statement = statement.where(
                    ReleaseQualificationModel.entity_id == entity_id
                )
            rows = list(
                (
                    await session.scalars(
                        statement.order_by(ReleaseQualificationModel.created_at.desc()).limit(200)
                    )
                ).all()
            )
            return [
                {
                    "id": str(item.id),
                    "target_type": item.target_type,
                    "entity_id": str(item.entity_id),
                    "target_snapshot_hash": item.target_snapshot_hash,
                    "agent_release_id": str(item.agent_release_id) if item.agent_release_id else None,
                    "network_version_id": str(item.network_version_id) if item.network_version_id else None,
                    "suite_version_id": str(item.suite_version_id),
                    "dataset_version_id": str(item.dataset_version_id),
                    "evaluation_run_id": str(item.evaluation_run_id),
                    "status": item.status,
                    "score": item.score,
                    "pass_rate": item.pass_rate,
                    "critical_failures": item.critical_failures,
                    "summary": item.summary,
                    "created_at": item.created_at,
                }
                for item in rows
            ]

    async def _resolve_target_dict(self, session, *, project_id: UUID, raw: dict[str, Any] | None):
        if not raw:
            raise ValidationError("Evaluation target is required")
        try:
            return await self._target_resolver.resolve(
                session,
                project_id=project_id,
                target_type=str(raw["target_type"]),
                source_type=str(raw["source_type"]),
                entity_id=UUID(str(raw["entity_id"])),
                version_id=UUID(str(raw["version_id"])) if raw.get("version_id") else None,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError("Evaluation target is invalid") from exc

    @staticmethod
    def _dataset_payload(dataset, version, case_count: int) -> dict[str, Any]:
        return {
            "id": str(dataset.id),
            "project_id": str(dataset.project_id),
            "name": dataset.name,
            "description": dataset.description,
            "status": dataset.status,
            "current_version_id": str(dataset.current_version_id) if dataset.current_version_id else None,
            "current_version": version.version if version else None,
            "content_hash": version.content_hash if version else None,
            "case_count": case_count,
            "created_at": dataset.created_at,
            "updated_at": dataset.updated_at,
        }

    @staticmethod
    def _case_payload(case) -> dict[str, Any]:
        return {
            "id": str(case.id),
            "position": case.position,
            "name": case.name,
            "input_payload": case.input_payload,
            "initial_context": case.initial_context,
            "expected_contract": case.expected_contract,
            "severity": case.severity,
            "weight": case.weight,
            "blocking": case.blocking,
            "tags": case.tags,
            "production_frequency": case.production_frequency,
        }

    @staticmethod
    def _suite_payload(suite, version) -> dict[str, Any]:
        return {
            "id": str(suite.id),
            "project_id": str(suite.project_id),
            "name": suite.name,
            "description": suite.description,
            "target_type": suite.target_type,
            "status": suite.status,
            "current_version_id": str(suite.current_version_id) if suite.current_version_id else None,
            "current_version": version.version if version else None,
            "dataset_version_id": str(version.dataset_version_id) if version else None,
            "judge_provider_model_id": str(version.judge_provider_model_id) if version else None,
            "judge_config": version.judge_config if version else None,
            "rubric": version.rubric if version else None,
            "acceptance_policy": version.acceptance_policy if version else None,
            "repetition_policy": version.repetition_policy if version else None,
            "estimate_defaults": version.estimate_defaults if version else None,
            "suite_hash": version.suite_hash if version else None,
            "created_at": suite.created_at,
            "updated_at": suite.updated_at,
        }

    @staticmethod
    def _target_payload(target) -> dict[str, Any]:
        return {
            "id": str(target.id),
            "side": target.side,
            "target_type": target.target_type,
            "source_type": target.source_type,
            "entity_id": str(target.entity_id),
            "environment": target.environment,
            "agent_release_id": str(target.agent_release_id) if target.agent_release_id else None,
            "network_version_id": str(target.network_version_id) if target.network_version_id else None,
            "snapshot_hash": target.snapshot_hash,
            "composition_hash": target.composition_hash,
            "display_name": target.display_name,
            "display_version": target.display_version,
        }

    def _run_payload(self, run, targets) -> dict[str, Any]:
        return {
            "id": str(run.id),
            "project_id": str(run.project_id),
            "suite_version_id": str(run.suite_version_id),
            "mode": run.mode,
            "status": run.status,
            "repetitions": run.repetitions,
            "qualification_status": run.qualification_status,
            "overall_score": run.overall_score,
            "pass_rate": run.pass_rate,
            "aggregate_result": run.aggregate_result,
            "estimated_preflight_cost": float(run.estimated_preflight_cost) if run.estimated_preflight_cost is not None else None,
            "measured_total_cost": float(run.measured_total_cost) if run.measured_total_cost is not None else None,
            "failure_code": run.failure_code,
            "failure_detail": run.failure_detail,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "created_at": run.created_at,
            "targets": [self._target_payload(item) for item in targets if item is not None],
        }
