from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.evaluation.application.durable_authoring import (
    DurableEvaluationSuiteAuthoringService,
)
from shared.infra.errors import ValidationError


class SecureEvaluationSuiteAuthoringService(DurableEvaluationSuiteAuthoringService):
    """Backend-authoritative authoring validation for every persistence path."""

    async def create_composed_suite(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str,
        target_type: str,
        judge_provider_model_id: UUID,
        cases_payload: dict[str, Any],
        judge_config: dict[str, Any],
        rubric: dict[str, Any],
        deterministic_checks: dict[str, Any],
        acceptance_policy: dict[str, Any],
        repetition_policy: dict[str, Any],
        estimate_defaults: dict[str, Any],
        authoring_source: str,
        source_snapshot_hash: str | None,
        source_context_hash: str | None,
        authoring_metadata: dict[str, Any] | None,
        created_by: UUID | None,
    ) -> dict[str, Any]:
        metadata = dict(authoring_metadata or {})
        reference_target = (
            metadata.get("reference_target")
            if isinstance(metadata.get("reference_target"), dict)
            else None
        )
        validation = await self.validate_draft(
            cases_payload,
            project_id=project_id,
            reference_target=reference_target,
        )
        if not validation.get("valid"):
            summary = "; ".join(
                f"{item.get('path')}: {item.get('message')}"
                for item in validation.get("errors", [])[:10]
            )
            raise ValidationError("Invalid target-bound Evaluator Suite: " + summary)

        reference = validation.get("reference") or {}
        if reference.get("mode") == "target_bound":
            resolved_snapshot_hash = reference.get("snapshot_hash")
            resolved_validation_context_hash = reference.get("context_hash")
            if source_snapshot_hash and source_snapshot_hash != resolved_snapshot_hash:
                raise ValidationError(
                    "Suite source_snapshot_hash does not match the validated target"
                )
            source_snapshot_hash = str(resolved_snapshot_hash or "") or None

            if authoring_source == "ai_generated":
                metadata["validation_context_hash"] = (
                    str(resolved_validation_context_hash or "") or None
                )
            else:
                if (
                    source_context_hash
                    and source_context_hash != resolved_validation_context_hash
                ):
                    raise ValidationError(
                        "Suite source_context_hash does not match the validated context"
                    )
                source_context_hash = (
                    str(resolved_validation_context_hash or "") or None
                )

        return await super().create_composed_suite(
            project_id=project_id,
            name=name,
            description=description,
            target_type=target_type,
            judge_provider_model_id=judge_provider_model_id,
            cases_payload={**cases_payload, "cases": validation.get("cases") or []},
            judge_config=judge_config,
            rubric=rubric,
            deterministic_checks=deterministic_checks,
            acceptance_policy=acceptance_policy,
            repetition_policy=repetition_policy,
            estimate_defaults=estimate_defaults,
            authoring_source=authoring_source,
            source_snapshot_hash=source_snapshot_hash,
            source_context_hash=source_context_hash,
            authoring_metadata={
                **metadata,
                "reference_validation": reference,
            },
            created_by=created_by,
        )


__all__ = ["SecureEvaluationSuiteAuthoringService"]
