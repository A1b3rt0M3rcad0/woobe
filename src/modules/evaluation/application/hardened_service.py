from __future__ import annotations

import random
from dataclasses import asdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from modules.evaluation.application.preflight import EvaluationPreflightService
from modules.evaluation.application.service import EvaluationApplicationService
from modules.evaluation.domain.enums import EvaluationMode, EvaluationRunStatus
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationSuiteModel,
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
)
from shared.infra.errors import ConflictError, NotFoundError, ValidationError


class HardenedEvaluationApplicationService(EvaluationApplicationService):
    """Control-plane safeguards around single-target Evaluation Runs."""

    _MAX_TARGET_RUNS = 5_000

    def __init__(self, session_factory) -> None:
        super().__init__(session_factory)
        self._preflight = EvaluationPreflightService()

    @staticmethod
    def _reject_legacy_baseline(baseline: dict[str, Any] | None) -> None:
        if baseline is not None:
            raise ValidationError(
                "An Evaluation Run tests exactly one snapshot. Use the Comparison endpoints "
                "to create two independent Runs or compare existing evidence."
            )

    async def preview_run(
        self,
        *,
        project_id: UUID,
        suite_version_id: UUID,
        repetitions: int,
        candidate: dict[str, Any],
        baseline: dict[str, Any] | None,
        acknowledge_tool_side_effects: bool = False,
        approved_high_risk_tool_ids: list[UUID] | None = None,
    ) -> dict[str, Any]:
        self._reject_legacy_baseline(baseline)
        base = await super().preview_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            candidate=candidate,
            baseline=None,
        )
        if int(base["target_run_count"]) > self._MAX_TARGET_RUNS:
            raise ValidationError(
                f"Evaluation exceeds the MVP limit of {self._MAX_TARGET_RUNS} target Runs"
            )

        async with self._session_factory() as session:
            suite = await session.get(EvaluationSuiteVersionModel, suite_version_id)
            if suite is None or suite.project_id != project_id:
                raise NotFoundError("Evaluation Suite version not found")
            suite_root = await session.get(EvaluationSuiteModel, suite.suite_id)
            if suite_root is None or suite_root.project_id != project_id:
                raise NotFoundError("Evaluation Suite not found")
            if suite_root.status == "archived":
                raise ConflictError("Archived Evaluation Suite cannot start new Runs")
            maximum_repetitions = int(
                (suite.repetition_policy or {}).get("maximum_repetitions", 25)
            )
            if repetitions > min(maximum_repetitions, 25):
                raise ValidationError(
                    f"Evaluation Suite allows at most {min(maximum_repetitions, 25)} repetitions"
                )
            target = await self._resolve_target_dict(
                session,
                project_id=project_id,
                raw=candidate,
            )
            preflight = await self._preflight.inspect(
                session,
                project_id=project_id,
                targets=[target],
                approved_high_risk_tool_ids=set(approved_high_risk_tool_ids or []),
            )

        return {
            **base,
            "mode": EvaluationMode.ABSOLUTE.value,
            "candidate": asdict(target),
            "baseline": None,
            "preflight": preflight.to_dict(),
            "requires_confirmation": (
                preflight.requires_acknowledgement
                and not acknowledge_tool_side_effects
            ),
            "can_execute": not preflight.blocked_high_risk_tool_ids
            and (
                acknowledge_tool_side_effects
                or not preflight.requires_acknowledgement
            ),
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
        acknowledge_tool_side_effects: bool = False,
        approved_high_risk_tool_ids: list[UUID] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        self._reject_legacy_baseline(baseline)
        preview = await self.preview_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            candidate=candidate,
            baseline=None,
            acknowledge_tool_side_effects=acknowledge_tool_side_effects,
            approved_high_risk_tool_ids=approved_high_risk_tool_ids,
        )
        if preview["preflight"]["blocked_high_risk_tool_ids"]:
            raise ConflictError(
                "Evaluation contains high-risk Tools without explicit approval"
            )
        if preview["requires_confirmation"]:
            raise ConflictError(
                "Evaluation executes real Tools. Confirm Tool side effects before starting"
            )

        normalized_key = idempotency_key.strip() if idempotency_key else None
        try:
            async with self._session_factory() as session, session.begin():
                if normalized_key:
                    existing = await session.scalar(
                        select(EvaluationRunModel).where(
                            EvaluationRunModel.project_id == project_id,
                            EvaluationRunModel.request_idempotency_key == normalized_key,
                        )
                    )
                    if existing is not None:
                        targets = await self._targets_for_run(session, existing.id)
                        return self._run_payload(existing, targets)

                suite = await session.get(EvaluationSuiteVersionModel, suite_version_id)
                if suite is None or suite.project_id != project_id:
                    raise NotFoundError("Evaluation Suite version not found")
                suite_root = await session.get(EvaluationSuiteModel, suite.suite_id)
                if suite_root is None or suite_root.project_id != project_id:
                    raise NotFoundError("Evaluation Suite not found")
                if suite_root.status == "archived":
                    raise ConflictError("Archived Evaluation Suite cannot start new Runs")
                target = await self._resolve_target_dict(
                    session,
                    project_id=project_id,
                    raw=candidate,
                )
                if target.target_type != suite_root.target_type:
                    raise ValidationError(
                        "Evaluation target type does not match the Evaluation Suite"
                    )

                run = EvaluationRunModel(
                    project_id=project_id,
                    suite_version_id=suite_version_id,
                    mode=EvaluationMode.ABSOLUTE.value,
                    status=EvaluationRunStatus.QUEUED.value,
                    repetitions=repetitions,
                    execution_order="randomized",
                    execution_policy={
                        "requested_parallel_pairs": 3,
                        "pair_members_serialized": False,
                        "single_target_invariant": True,
                    },
                    randomization_seed=random.SystemRandom().randint(1, 2_147_483_647),
                    request_idempotency_key=normalized_key,
                    requested_by=requested_by,
                    aggregate_result={
                        "_request": {
                            "idempotency_key": normalized_key,
                            "acknowledge_tool_side_effects": acknowledge_tool_side_effects,
                            "approved_high_risk_tool_ids": [
                                str(value)
                                for value in (approved_high_risk_tool_ids or [])
                            ],
                        },
                        "preflight": preview["preflight"],
                    },
                )
                session.add(run)
                await session.flush()
                target_model = EvaluationTargetModel(
                    evaluation_run_id=run.id,
                    project_id=project_id,
                    side="single",
                    **asdict(target),
                )
                session.add(target_model)
                await session.flush()
                run.candidate_target_id = target_model.id
                run.baseline_target_id = None
                return self._run_payload(run, [target_model])
        except IntegrityError:
            if not normalized_key:
                raise
            async with self._session_factory() as session:
                existing = await session.scalar(
                    select(EvaluationRunModel).where(
                        EvaluationRunModel.project_id == project_id,
                        EvaluationRunModel.request_idempotency_key == normalized_key,
                    )
                )
                if existing is None:
                    raise
                targets = await self._targets_for_run(session, existing.id)
                return self._run_payload(existing, targets)

    @staticmethod
    async def _targets_for_run(session, run_id: UUID):
        return list(
            (
                await session.scalars(
                    select(EvaluationTargetModel).where(
                        EvaluationTargetModel.evaluation_run_id == run_id
                    )
                )
            ).all()
        )


__all__ = ["HardenedEvaluationApplicationService"]
