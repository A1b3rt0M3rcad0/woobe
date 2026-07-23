from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.agent.infra.database.models import ProviderCredentialModel
from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.evaluation.application.experience_service import EvaluationExperienceService
from modules.evaluation.application.failure_taxonomy import (
    canonical_judge_failure_code,
    judge_failure_policy,
)
from modules.evaluation.application.judge_policy import (
    judge_model_snapshot,
    normalized_judge_config,
)
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationSuiteModel,
    EvaluationSuiteVersionModel,
    EvaluationTrialModel,
    EvaluatorModelCallModel,
)
from modules.evaluation.infra.judge import canonical_hash
from shared.infra.errors import ConflictError, NotFoundError


def _next_version(value: str | None) -> str:
    try:
        number = int(str(value or "v0").removeprefix("v"))
    except ValueError:
        number = 0
    return f"v{number + 1}"


class GovernedEvaluationExperienceService(EvaluationExperienceService):
    """Freeze the selected Judge Model and reject structurally invalid retries."""

    async def _govern_judge_config(
        self,
        *,
        project_id: UUID,
        judge_provider_model_id: UUID,
        judge_config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            model = await session.get(ProviderModelModel, judge_provider_model_id)
            if model is None or model.project_id != project_id:
                raise NotFoundError("Judge Model not found in this Project")
            credential = await session.get(
                ProviderCredentialModel,
                model.provider_credential_id,
            )
            if credential is None or credential.project_id != project_id:
                raise NotFoundError("Judge Model credential not found in this Project")
            if model.status != "active":
                raise ConflictError("The selected Judge Model is not active")
            if credential.status != "active":
                raise ConflictError("The selected Judge Model credential is not active")
            normalized = normalized_judge_config(model.meta or {}, judge_config or {})
            snapshot = judge_model_snapshot(
                model,
                credential,
                judge_config=normalized,
            )
        return {
            **normalized,
            "judge_model_snapshot": snapshot,
            "judge_model_snapshot_hash": snapshot["snapshot_hash"],
            "judge_protocol_version": "governed-judge-protocol-v1",
        }

    async def create_suite(self, **kwargs: Any) -> dict[str, Any]:
        kwargs["judge_config"] = await self._govern_judge_config(
            project_id=kwargs["project_id"],
            judge_provider_model_id=kwargs["judge_provider_model_id"],
            judge_config=kwargs.get("judge_config"),
        )
        return await super().create_suite(**kwargs)

    async def create_composed_suite_version(self, **kwargs: Any) -> dict[str, Any]:
        project_id = kwargs["project_id"]
        judge_model_id = kwargs.get("judge_provider_model_id")
        judge_config = kwargs.get("judge_config")
        if judge_model_id is None:
            async with self._session_factory() as session:
                suite = await session.get(EvaluationSuiteModel, kwargs["suite_id"])
                if suite is None or suite.project_id != project_id:
                    raise NotFoundError("Evaluation Suite not found")
                if suite.current_version_id is None:
                    raise NotFoundError("Current Evaluation Suite version not found")
                current = await session.get(
                    EvaluationSuiteVersionModel,
                    suite.current_version_id,
                )
                if current is None:
                    raise NotFoundError("Current Evaluation Suite version not found")
                judge_model_id = current.judge_provider_model_id
                if judge_config is None:
                    judge_config = dict(current.judge_config or {})
        kwargs["judge_provider_model_id"] = judge_model_id
        kwargs["judge_config"] = await self._govern_judge_config(
            project_id=project_id,
            judge_provider_model_id=judge_model_id,
            judge_config=judge_config,
        )
        return await super().create_composed_suite_version(**kwargs)

    async def create_judge_model_suite_version(
        self,
        *,
        project_id: UUID,
        suite_id: UUID,
        judge_provider_model_id: UUID,
        change_description: str,
        created_by: UUID | None,
    ) -> dict[str, Any]:
        description = change_description.strip()
        if len(description) < 3:
            raise ConflictError("Suite Version change description is required")

        async with self._session_factory() as session:
            suite = await session.get(EvaluationSuiteModel, suite_id)
            if suite is None or suite.project_id != project_id:
                raise NotFoundError("Evaluation Suite not found")
            if suite.status == "archived":
                raise ConflictError("Archived Evaluation Suite cannot receive a new version")
            if suite.current_version_id is None:
                raise NotFoundError("Current Evaluation Suite version not found")
            current = await session.get(
                EvaluationSuiteVersionModel,
                suite.current_version_id,
            )
            if current is None:
                raise NotFoundError("Current Evaluation Suite version not found")
            if current.judge_provider_model_id == judge_provider_model_id:
                raise ConflictError("The selected Judge Model is already used by the current Suite Version")
            governed_config = await self._govern_judge_config(
                project_id=project_id,
                judge_provider_model_id=judge_provider_model_id,
                judge_config=dict(current.judge_config or {}),
            )

        async with self._session_factory() as session, session.begin():
            suite = await session.get(
                EvaluationSuiteModel,
                suite_id,
                with_for_update=True,
            )
            if suite is None or suite.project_id != project_id:
                raise NotFoundError("Evaluation Suite not found")
            if suite.status == "archived":
                raise ConflictError("Archived Evaluation Suite cannot receive a new version")
            if suite.current_version_id is None:
                raise NotFoundError("Current Evaluation Suite version not found")
            current = await session.get(
                EvaluationSuiteVersionModel,
                suite.current_version_id,
                with_for_update=True,
            )
            if current is None:
                raise NotFoundError("Current Evaluation Suite version not found")
            if current.judge_provider_model_id == judge_provider_model_id:
                raise ConflictError("The selected Judge Model is already used by the current Suite Version")

            material = {
                "dataset_version_id": str(current.dataset_version_id),
                "judge_provider_model_id": str(judge_provider_model_id),
                "judge_config": governed_config,
                "rubric": current.rubric or {},
                "deterministic_checks": current.deterministic_checks or {},
                "acceptance_policy": current.acceptance_policy or {},
                "repetition_policy": current.repetition_policy or {},
                "estimate_defaults": current.estimate_defaults or {},
            }
            version = EvaluationSuiteVersionModel(
                suite_id=suite.id,
                project_id=project_id,
                version=_next_version(current.version),
                parent_version_id=current.id,
                change_description=description,
                dataset_version_id=current.dataset_version_id,
                judge_provider_model_id=judge_provider_model_id,
                judge_config=governed_config,
                rubric=current.rubric or {},
                deterministic_checks=current.deterministic_checks or {},
                acceptance_policy=current.acceptance_policy or {},
                repetition_policy=current.repetition_policy or {},
                estimate_defaults=current.estimate_defaults or {},
                suite_hash=canonical_hash(material),
                created_by=created_by,
            )
            session.add(version)
            await session.flush()
            suite.current_version_id = version.id

        values = await self.list_suites(project_id, include_archived=True)
        return next(item for item in values if item["id"] == str(suite_id))

    async def _assert_retry_allowed(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        trial_ids: list[UUID] | None = None,
    ) -> None:
        selected = set(trial_ids or [])
        async with self._session_factory() as session:
            run = await session.get(EvaluationRunModel, run_id)
            if run is None or run.project_id != project_id:
                raise NotFoundError("Evaluation Run not found")
            trials = list(
                (
                    await session.scalars(
                        select(EvaluationTrialModel).where(
                            EvaluationTrialModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            calls = list(
                (
                    await session.scalars(
                        select(EvaluatorModelCallModel).where(
                            EvaluatorModelCallModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
        calls_by_trial = {call.evaluation_trial_id: call for call in calls}
        terminal: list[tuple[str, dict[str, Any]]] = []
        for trial in trials:
            if selected and trial.id not in selected:
                continue
            call = calls_by_trial.get(trial.id)
            code = canonical_judge_failure_code(
                failure_code=trial.failure_code,
                failure_detail=trial.failure_detail,
                judge_status=call.status if call else None,
                judge_error=call.error if call else None,
            )
            policy = judge_failure_policy(code)
            if code and not policy.get("retryable"):
                terminal.append((code, policy))
        if terminal:
            code, policy = terminal[0]
            raise ConflictError(
                f"Judge retry is blocked for {code}. "
                f"{policy.get('recommended_action') or 'Change the Judge configuration first.'}"
            )

    async def retry_judgments(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        trial_ids: list[UUID] | None = None,
        failure_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        await self._assert_retry_allowed(
            project_id=project_id,
            run_id=run_id,
            trial_ids=trial_ids,
        )
        return await super().retry_judgments(
            project_id=project_id,
            run_id=run_id,
            trial_ids=trial_ids,
            failure_codes=failure_codes,
        )


__all__ = ["GovernedEvaluationExperienceService"]
