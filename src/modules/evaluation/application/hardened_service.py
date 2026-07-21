from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.evaluation.application.preflight import EvaluationPreflightService
from modules.evaluation.application.service import EvaluationApplicationService
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationSuiteVersionModel,
)
from shared.infra.errors import ConflictError, NotFoundError, ValidationError


class HardenedEvaluationApplicationService(EvaluationApplicationService):
    """Control-plane safeguards around the Evaluation application service."""

    _MAX_TARGET_RUNS = 5_000

    def __init__(self, session_factory) -> None:
        super().__init__(session_factory)
        self._preflight = EvaluationPreflightService()

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
        base = await super().preview_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            candidate=candidate,
            baseline=baseline,
        )
        if int(base["target_run_count"]) > self._MAX_TARGET_RUNS:
            raise ValidationError(
                f"Evaluation exceeds the MVP limit of {self._MAX_TARGET_RUNS} target Runs"
            )

        async with self._session_factory() as session:
            suite = await session.get(EvaluationSuiteVersionModel, suite_version_id)
            if suite is None or suite.project_id != project_id:
                raise NotFoundError("Evaluation Suite version not found")
            maximum_repetitions = int(
                (suite.repetition_policy or {}).get("maximum_repetitions", 25)
            )
            if repetitions > min(maximum_repetitions, 25):
                raise ValidationError(
                    f"Evaluation Suite allows at most {min(maximum_repetitions, 25)} repetitions"
                )
            candidate_target = await self._resolve_target_dict(
                session,
                project_id=project_id,
                raw=candidate,
            )
            baseline_target = (
                await self._resolve_target_dict(
                    session,
                    project_id=project_id,
                    raw=baseline,
                )
                if baseline
                else None
            )
            if (
                baseline_target is not None
                and baseline_target.snapshot_hash == candidate_target.snapshot_hash
            ):
                raise ConflictError(
                    "Candidate and Baseline resolve to the same immutable snapshot"
                )
            targets = [candidate_target]
            if baseline_target is not None:
                targets.append(baseline_target)
            preflight = await self._preflight.inspect(
                session,
                project_id=project_id,
                targets=targets,
                approved_high_risk_tool_ids=set(approved_high_risk_tool_ids or []),
            )

        preflight_payload = preflight.to_dict()
        return {
            **base,
            "preflight": preflight_payload,
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
        preview = await self.preview_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            candidate=candidate,
            baseline=baseline,
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
        if normalized_key:
            async with self._session_factory() as session:
                existing = await session.scalar(
                    select(EvaluationRunModel)
                    .where(
                        EvaluationRunModel.project_id == project_id,
                        EvaluationRunModel.aggregate_result["_request"][
                            "idempotency_key"
                        ].astext
                        == normalized_key,
                    )
                    .order_by(EvaluationRunModel.created_at.desc())
                    .limit(1)
                )
                if existing is not None:
                    targets = await self._targets_for_run(session, existing.id)
                    return self._run_payload(existing, targets)

        created = await super().create_run(
            project_id=project_id,
            suite_version_id=suite_version_id,
            repetitions=repetitions,
            candidate=candidate,
            baseline=baseline,
            requested_by=requested_by,
        )
        async with self._session_factory() as session, session.begin():
            run = await session.get(
                EvaluationRunModel,
                UUID(created["id"]),
                with_for_update=True,
            )
            if run is None:
                raise NotFoundError("Evaluation Run was not persisted")
            run.aggregate_result = {
                "_request": {
                    "idempotency_key": normalized_key,
                    "acknowledge_tool_side_effects": acknowledge_tool_side_effects,
                    "approved_high_risk_tool_ids": [
                        str(value) for value in (approved_high_risk_tool_ids or [])
                    ],
                },
                "preflight": preview["preflight"],
            }
            run.estimated_preflight_cost = None
            await session.flush()
            targets = await self._targets_for_run(session, run.id)
            return self._run_payload(run, targets)

    @staticmethod
    async def _targets_for_run(session, run_id: UUID):
        from modules.evaluation.infra.database.models import EvaluationTargetModel

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
