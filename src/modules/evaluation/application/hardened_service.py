from __future__ import annotations

import random
from dataclasses import asdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from modules.evaluation.application.judge_affordability import (
    JudgeAffordabilityService,
)
from modules.evaluation.application.judge_policy import JudgePreflightService
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
        self._judge_preflight = JudgePreflightService()
        self._judge_affordability = JudgeAffordabilityService()

    @staticmethod
    def _reject_legacy_baseline(baseline: dict[str, Any] | None) -> None:
        if baseline is not None:
            raise ValidationError(
                "An Evaluation Run tests exactly one snapshot. Use the Comparison endpoints "
                "to create two independent Runs or compare existing evidence."
            )

    @staticmethod
    def _merge_affordability(
        judge_preflight: dict[str, Any],
        affordability: dict[str, Any],
    ) -> dict[str, Any]:
        blockers = [
            item
            for item in judge_preflight.get("blockers") or []
            if isinstance(item, dict)
        ]
        warnings = [
            item
            for item in judge_preflight.get("warnings") or []
            if isinstance(item, dict)
        ]
        live_status = str(affordability.get("status") or "unknown")
        if live_status == "ready":
            warnings = [
                item
                for item in warnings
                if item.get("code") != "judge_affordability_unknown"
            ]
        for item in affordability.get("blockers") or []:
            if isinstance(item, dict) and item not in blockers:
                blockers.append(item)
        for item in affordability.get("warnings") or []:
            if isinstance(item, dict) and item not in warnings:
                warnings.append(item)
        merged = {
            **judge_preflight,
            "status": "blocked" if blockers else "ready",
            "can_execute": not blockers,
            "blockers": blockers,
            "warnings": warnings,
            "affordability": affordability,
        }
        if affordability.get("limit_remaining_usd") is not None:
            merged["credential_remaining_usd"] = affordability[
                "limit_remaining_usd"
            ]
        return merged

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
            judge_preflight = await self._judge_preflight.inspect_suite(
                session,
                project_id=project_id,
                suite_version=suite,
                repetitions=repetitions,
                target_count=1,
            )
            affordability = await self._judge_affordability.inspect(
                session,
                project_id=project_id,
                provider_model_id=suite.judge_provider_model_id,
                estimated_maximum_cost_usd=judge_preflight.get(
                    "estimated_maximum_cost_usd"
                ),
            )
            judge_preflight = self._merge_affordability(
                judge_preflight,
                affordability,
            )

        tool_can_execute = not preflight.blocked_high_risk_tool_ids and (
            acknowledge_tool_side_effects or not preflight.requires_acknowledgement
        )
        return {
            **base,
            "mode": EvaluationMode.ABSOLUTE.value,
            "candidate": asdict(target),
            "baseline": None,
            "preflight": preflight.to_dict(),
            "judge_preflight": judge_preflight,
            "requires_confirmation": (
                preflight.requires_acknowledgement
                and not acknowledge_tool_side_effects
            ),
            "can_execute": tool_can_execute and bool(judge_preflight.get("can_execute")),
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
        judge_preflight = preview.get("judge_preflight") or {}
        if not judge_preflight.get("can_execute"):
            blockers = judge_preflight.get("blockers") or []
            detail = "; ".join(
                str(item.get("message") or item.get("code"))
                for item in blockers
                if isinstance(item, dict)
            )
            raise ConflictError(
                "Judge Model preflight blocked this Evaluation"
                + (f": {detail}" if detail else "")
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
                        "judge_canary_required": True,
                        "judge_circuit_breaker_enabled": True,
                        "judge_preflight_hash": judge_preflight.get("preflight_hash"),
                        "judge_protocol": {
                            "judge_model_snapshot_hash": (
                                (judge_preflight.get("judge_model") or {}).get(
                                    "snapshot_hash"
                                )
                            ),
                            "normalized_judge_config": judge_preflight.get(
                                "normalized_judge_config"
                            ),
                        },
                    },
                    randomization_seed=random.SystemRandom().randint(1, 2_147_483_647),
                    request_idempotency_key=normalized_key,
                    requested_by=requested_by,
                    estimated_preflight_cost=judge_preflight.get(
                        "estimated_maximum_cost_usd"
                    ),
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
                        "judge_preflight": judge_preflight,
                        "judge_canary": {"status": "pending"},
                        "judge_circuit_breaker": {"status": "closed"},
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
