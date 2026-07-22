from __future__ import annotations

from typing import Any

from modules.evaluation.application.completed_service import (
    CompletedEvaluationApplicationService,
)
from modules.evaluation.application.contract_aware_authoring import (
    ContractAwareEvaluationSuiteAuthoringService,
)
from shared.infra.errors import ValidationError


class FinalEvaluationApplicationService(CompletedEvaluationApplicationService):
    """Operational facade with backend-authoritative composed version validation."""

    async def create_composed_suite_version(self, **kwargs) -> dict[str, Any]:
        project_id = kwargs["project_id"]
        draft = kwargs["draft"]
        authoring_source = str(kwargs.get("authoring_source") or "manual")
        metadata = dict(kwargs.get("authoring_metadata") or {})
        reference_target = (
            metadata.get("reference_target")
            if isinstance(metadata.get("reference_target"), dict)
            else None
        )
        validator = ContractAwareEvaluationSuiteAuthoringService(
            self._session_factory
        )
        validation = await validator.validate_draft(
            draft,
            project_id=project_id,
            reference_target=reference_target,
        )
        if not validation.get("valid"):
            summary = "; ".join(
                f"{item.get('path')}: {item.get('message')}"
                for item in validation.get("errors", [])[:10]
            )
            raise ValidationError("Invalid target-bound Suite version: " + summary)

        reference = validation.get("reference") or {}
        if reference.get("mode") == "target_bound":
            resolved_snapshot_hash = reference.get("snapshot_hash")
            resolved_validation_context_hash = reference.get("context_hash")
            supplied_snapshot_hash = kwargs.get("source_snapshot_hash")
            supplied_context_hash = kwargs.get("source_context_hash")
            if supplied_snapshot_hash and supplied_snapshot_hash != resolved_snapshot_hash:
                raise ValidationError(
                    "Suite source_snapshot_hash does not match the validated target"
                )
            kwargs["source_snapshot_hash"] = str(resolved_snapshot_hash or "") or None

            if authoring_source == "ai_generated":
                metadata["validation_context_hash"] = (
                    str(resolved_validation_context_hash or "") or None
                )
            else:
                if (
                    supplied_context_hash
                    and supplied_context_hash != resolved_validation_context_hash
                ):
                    raise ValidationError(
                        "Suite source_context_hash does not match the validated context"
                    )
                kwargs["source_context_hash"] = (
                    str(resolved_validation_context_hash or "") or None
                )

        kwargs["draft"] = {**draft, "cases": validation.get("cases") or []}
        kwargs["authoring_metadata"] = {
            **metadata,
            "normalization_warnings": validation.get("normalization_warnings", []),
            "reference_validation": reference,
        }
        return await super().create_composed_suite_version(**kwargs)


__all__ = ["FinalEvaluationApplicationService"]
