from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.evaluation.application.diagnostic_authoring import (
    DiagnosticEvaluationSuiteAuthoringService,
)
from modules.evaluation.infra.judge import canonical_hash


class ContractAwareEvaluationSuiteAuthoringService(
    DiagnosticEvaluationSuiteAuthoringService
):
    """Normalize target-bound Test Cases against the frozen output contract."""

    async def validate_draft(
        self,
        payload: dict[str, Any],
        *,
        project_id: UUID | None = None,
        reference_target: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        validation = await super().validate_draft(
            payload,
            project_id=project_id,
            reference_target=reference_target,
        )
        if reference_target is None or project_id is None:
            return validation

        async with self._session_factory() as session:
            resolved = await self._target_resolver.resolve(
                session,
                project_id=project_id,
                target_type=str(reference_target.get("target_type") or "agent"),
                source_type=str(reference_target.get("source_type") or "draft"),
                entity_id=UUID(str(reference_target["entity_id"])),
                version_id=(
                    UUID(str(reference_target["version_id"]))
                    if reference_target.get("version_id")
                    else None
                ),
            )

        output_schema = resolved.snapshot.get("output_schema")
        semantic_only = (
            str(reference_target.get("output_contract_mode") or "").lower()
            == "semantic_only"
        )
        cases = [dict(item) for item in validation.get("cases") or []]
        warnings = list(validation.get("warnings") or [])
        normalization = list(validation.get("normalization_warnings") or [])
        enforced = 0

        if isinstance(output_schema, dict) and output_schema and not semantic_only:
            schema_hash = canonical_hash(output_schema)
            for index, case in enumerate(cases):
                expected = (
                    dict(case.get("expected_contract"))
                    if isinstance(case.get("expected_contract"), dict)
                    else {}
                )
                contract = (
                    dict(expected.get("output_contract"))
                    if isinstance(expected.get("output_contract"), dict)
                    else {}
                )
                if not contract.get("json_required") or not contract.get("schema"):
                    contract.update(
                        {
                            "required": True,
                            "json_required": True,
                            "schema": output_schema,
                            "schema_hash": schema_hash,
                            "source": "target_snapshot",
                        }
                    )
                    expected["output_contract"] = contract
                    case["expected_contract"] = expected
                    enforced += 1
                    normalization.append(
                        {
                            "path": f"cases[{index}].expected_contract.output_contract",
                            "code": "target_output_contract_inherited",
                            "message": (
                                "Structured Output validation was inherited from the exact target snapshot."
                            ),
                        }
                    )
        elif isinstance(output_schema, dict) and output_schema and semantic_only:
            warnings.append(
                {
                    "path": "reference_target.output_contract_mode",
                    "code": "structured_output_validation_disabled",
                    "message": (
                        "This Suite explicitly evaluates semantic content only and does not validate the target Structured Output schema."
                    ),
                }
            )

        reference = dict(validation.get("reference") or {})
        reference["output_contract"] = {
            "has_schema": bool(output_schema),
            "schema_hash": canonical_hash(output_schema) if output_schema else None,
            "mode": "semantic_only" if semantic_only else (
                "target_schema" if output_schema else "none"
            ),
            "cases_normalized": enforced,
        }
        return {
            **validation,
            "cases": cases,
            "warnings": warnings,
            "normalization_warnings": normalization,
            "reference": reference,
        }


__all__ = ["ContractAwareEvaluationSuiteAuthoringService"]
