from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.agent.infra.database.models import ProviderCredentialModel
from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.evaluation.application.context_pack import EvaluationContextPackBuilder
from modules.evaluation.application.target_resolver import EvaluationTargetResolver
from modules.evaluation.application.token_budget import (
    context_window_from_metadata,
    recommended_generation_output_tokens,
)
from modules.evaluation.domain.contracts import validate_suite_draft
from modules.evaluation.infra.database.models import (
    EvaluationAuthoringCallModel,
    EvaluationDatasetModel,
    EvaluationDatasetVersionModel,
    EvaluationSuiteModel,
    EvaluationSuiteVersionModel,
    EvaluationTestCaseModel,
)
from modules.evaluation.infra.generator import SuiteGeneratorGateway
from modules.evaluation.infra.judge import canonical_hash
from shared.infra.errors import ConflictError, NotFoundError, ValidationError
from shared.infra.llm_cost import calculate_llm_cost, provider_model_pricing_snapshot


DEFAULT_COVERAGE = (
    "core_behavior",
    "edge_cases",
    "tools",
    "knowledge",
    "security_refusal",
    "output_contract",
    "error_handling",
)


def _allocate_coverage(
    case_count: int,
    requested: dict[str, Any] | None,
    error_case_ratio: float,
) -> dict[str, int]:
    requested = requested or {}
    explicit: dict[str, int] = {}
    for key, raw in requested.items():
        try:
            value = max(0, int(raw))
        except (TypeError, ValueError):
            continue
        if value:
            explicit[str(key)] = value
    if explicit:
        total = sum(explicit.values())
        if total == case_count:
            return explicit
        if total > 0:
            scaled = {
                key: max(0, round(value / total * case_count))
                for key, value in explicit.items()
            }
            delta = case_count - sum(scaled.values())
            keys = list(scaled) or ["core_behavior"]
            for index in range(abs(delta)):
                key = keys[index % len(keys)]
                scaled[key] = max(0, scaled[key] + (1 if delta > 0 else -1))
            return scaled

    negative = max(0, min(case_count, round(case_count * error_case_ratio)))
    positive = case_count - negative
    result = {key: 0 for key in DEFAULT_COVERAGE}
    positive_keys = ["core_behavior", "edge_cases", "tools", "knowledge", "output_contract"]
    for index in range(positive):
        result[positive_keys[index % len(positive_keys)]] += 1
    negative_keys = ["security_refusal", "error_handling"]
    for index in range(negative):
        result[negative_keys[index % len(negative_keys)]] += 1
    return {key: value for key, value in result.items() if value > 0}


def _tool_names_from_context(context_pack: dict[str, Any]) -> set[str]:
    values = context_pack.get("tools")
    if not isinstance(values, list):
        return set()
    return {
        str(item.get("name") or "").strip().lower()
        for item in values
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }


def _validate_tool_references(
    validation: dict[str, Any],
    *,
    context_pack: dict[str, Any],
) -> dict[str, Any]:
    known = _tool_names_from_context(context_pack)
    errors = list(validation.get("errors") or [])
    warnings = list(validation.get("warnings") or [])
    for index, case in enumerate(validation.get("cases") or []):
        contract = case.get("expected_contract") if isinstance(case, dict) else None
        tools = contract.get("tools") if isinstance(contract, dict) else None
        if not isinstance(tools, dict):
            continue
        for field in ("required", "forbidden"):
            values = tools.get(field)
            if not isinstance(values, list):
                continue
            for value in values:
                name = str(value).strip()
                if not name:
                    continue
                if not known:
                    warnings.append(
                        {
                            "path": f"cases[{index}].expected_contract.tools.{field}",
                            "code": "tool_catalog_unavailable",
                            "message": (
                                f"Tool '{name}' could not be verified because the selected "
                                "snapshot exposes no Tool catalog."
                            ),
                        }
                    )
                elif name.lower() not in known:
                    errors.append(
                        {
                            "path": f"cases[{index}].expected_contract.tools.{field}",
                            "code": "unknown_tool",
                            "message": f"Tool '{name}' is not available in the selected snapshot.",
                        }
                    )
    return {
        **validation,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }


class EvaluationSuiteAuthoringService:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory
        self._target_resolver = EvaluationTargetResolver(session_factory)
        self._context_builder = EvaluationContextPackBuilder()
        self._generator = SuiteGeneratorGateway()

    async def preview_context(
        self,
        *,
        project_id: UUID,
        target: dict[str, Any],
        generator_provider_model_id: UUID,
        objective: str,
        case_count: int,
        maximum_input_tokens: int,
    ) -> dict[str, Any]:
        case_count = self._validate_case_count(case_count)
        objective = objective.strip()
        if len(objective) < 10:
            raise ValidationError("Suite generation objective must contain at least 10 characters")
        async with self._session_factory() as session:
            provider_model = await self._provider_model(
                session,
                project_id=project_id,
                provider_model_id=generator_provider_model_id,
            )
            credential = await self._provider_credential(
                session,
                project_id=project_id,
                credential_id=provider_model.provider_credential_id,
            )
            resolved = await self._target_resolver.resolve(
                session,
                project_id=project_id,
                target_type=str(target.get("target_type") or "agent"),
                source_type=str(target.get("source_type") or "draft"),
                entity_id=UUID(str(target["entity_id"])),
                version_id=UUID(str(target["version_id"])) if target.get("version_id") else None,
            )
            output_tokens = recommended_generation_output_tokens(case_count)
            context_window = context_window_from_metadata(provider_model.meta or {})
            pack = await self._context_builder.build(
                session,
                project_id=project_id,
                target=resolved,
                objective=objective,
                maximum_input_tokens=maximum_input_tokens,
                reserved_output_tokens=output_tokens,
                context_window=context_window,
            )
            pricing = provider_model_pricing_snapshot(
                provider_model_id=provider_model.id,
                provider_credential_id=provider_model.provider_credential_id,
                provider=credential.provider,
                model=provider_model.model,
                metadata=provider_model.meta or {},
            )
            estimate = calculate_llm_cost(
                input_tokens=pack.budget.get("estimated_input_tokens"),
                output_tokens=output_tokens,
                pricing_snapshot=pricing,
            )
            return {
                "target": {
                    "target_type": resolved.target_type,
                    "source_type": resolved.source_type,
                    "entity_id": str(resolved.entity_id),
                    "display_name": resolved.display_name,
                    "display_version": resolved.display_version,
                    "snapshot_hash": resolved.snapshot_hash,
                },
                "generator": {
                    "provider_model_id": str(provider_model.id),
                    "provider": credential.provider,
                    "model": provider_model.model,
                },
                "context_hash": pack.context_hash,
                "context_budget": pack.budget,
                "context_sections": list(pack.payload.keys()),
                "available_tools": sorted(_tool_names_from_context(pack.payload)),
                "reserved_output_tokens": output_tokens,
                "context_window": context_window,
                "estimated_cost_usd": estimate["cost_usd"],
                "cost_status": estimate["cost_status"],
                "cost_reason": estimate["cost_reason"],
            }

    async def generate_draft(
        self,
        *,
        project_id: UUID,
        target: dict[str, Any],
        generator_provider_model_id: UUID,
        objective: str,
        case_count: int,
        coverage: dict[str, Any] | None,
        error_case_ratio: float,
        language: str,
        maximum_input_tokens: int,
        maximum_cost_usd: float | None,
        created_by: UUID | None,
    ) -> dict[str, Any]:
        case_count = self._validate_case_count(case_count)
        objective = objective.strip()
        if len(objective) < 10:
            raise ValidationError("Suite generation objective must contain at least 10 characters")
        error_case_ratio = max(0.0, min(float(error_case_ratio), 0.8))
        allocation = _allocate_coverage(case_count, coverage, error_case_ratio)

        async with self._session_factory() as session, session.begin():
            provider_model = await self._provider_model(
                session,
                project_id=project_id,
                provider_model_id=generator_provider_model_id,
            )
            credential = await self._provider_credential(
                session,
                project_id=project_id,
                credential_id=provider_model.provider_credential_id,
            )
            resolved = await self._target_resolver.resolve(
                session,
                project_id=project_id,
                target_type=str(target.get("target_type") or "agent"),
                source_type=str(target.get("source_type") or "draft"),
                entity_id=UUID(str(target["entity_id"])),
                version_id=UUID(str(target["version_id"])) if target.get("version_id") else None,
            )
            output_tokens = recommended_generation_output_tokens(case_count)
            context_window = context_window_from_metadata(provider_model.meta or {})
            pack = await self._context_builder.build(
                session,
                project_id=project_id,
                target=resolved,
                objective=objective,
                maximum_input_tokens=maximum_input_tokens,
                reserved_output_tokens=output_tokens,
                context_window=context_window,
            )
            call = EvaluationAuthoringCallModel(
                project_id=project_id,
                target_type=resolved.target_type,
                target_entity_id=resolved.entity_id,
                target_source_type=resolved.source_type,
                target_version_id=UUID(str(target["version_id"])) if target.get("version_id") else None,
                target_snapshot_hash=resolved.snapshot_hash,
                generator_provider_model_id=provider_model.id,
                generator_provider_credential_id=provider_model.provider_credential_id,
                provider=credential.provider,
                model=provider_model.model,
                objective=objective,
                requested_case_count=case_count,
                coverage_request={
                    "allocation": allocation,
                    "error_case_ratio": error_case_ratio,
                    "language": language,
                },
                status="running",
                prompt_version=self._generator.PROMPT_VERSION,
                context_hash=pack.context_hash,
                context_stats=pack.budget,
                created_by=created_by,
            )
            session.add(call)
            await session.flush()
            call_id = call.id
            provider_model_id = provider_model.id
            pack_payload = pack.payload
            snapshot_hash = resolved.snapshot_hash
            context_hash = pack.context_hash

        async with self._session_factory() as session:
            generated = await self._generator.generate(
                session,
                project_id=project_id,
                provider_model_id=provider_model_id,
                context_pack=pack_payload,
                objective=objective,
                case_count=case_count,
                coverage=allocation,
                error_case_ratio=error_case_ratio,
                language=language,
                maximum_cost_usd=maximum_cost_usd,
            )

        payload = generated.payload or {}
        validation = (
            validate_suite_draft(payload)
            if generated.payload
            else {
                "valid": False,
                "errors": [
                    {
                        "path": "generator",
                        "message": generated.error or "Generator returned no payload",
                    }
                ],
                "warnings": [],
                "coverage": {},
                "case_count": 0,
                "cases": [],
            }
        )
        if generated.payload:
            validation = _validate_tool_references(validation, context_pack=pack_payload)
        if validation["valid"] and validation["case_count"] != case_count:
            validation["warnings"] = [
                *validation["warnings"],
                {
                    "code": "case_count_mismatch",
                    "message": (
                        f"Generator returned {validation['case_count']} of "
                        f"{case_count} requested cases"
                    ),
                },
            ]
        draft = {
            "schema_version": 1,
            "suite": payload.get("suite") if isinstance(payload.get("suite"), dict) else {},
            "coverage": (
                payload.get("coverage")
                if isinstance(payload.get("coverage"), dict)
                else allocation
            ),
            "cases": validation["cases"],
        }

        async with self._session_factory() as session, session.begin():
            row = await session.get(EvaluationAuthoringCallModel, call_id, with_for_update=True)
            if row is not None:
                row.provider = generated.provider
                row.model = generated.model
                row.status = (
                    "completed" if generated.payload and validation["valid"] else "failed"
                )
                row.input_tokens = generated.input_tokens
                row.output_tokens = generated.output_tokens
                row.cost_usd = generated.cost_usd
                row.pricing_snapshot = generated.pricing_snapshot
                row.generated_payload = draft if generated.payload else None
                row.validation_result = validation
                row.error = generated.error
                row.completed_at = generated.completed_at

        return {
            "authoring_call_id": str(call_id),
            "authoring_source": "ai_generated",
            "source_snapshot_hash": snapshot_hash,
            "source_context_hash": context_hash,
            "generator": {
                "provider_model_id": str(generated.provider_model_id),
                "provider": generated.provider,
                "model": generated.model,
                "input_tokens": generated.input_tokens,
                "output_tokens": generated.output_tokens,
                "cost_usd": generated.cost_usd,
                "latency_ms": generated.latency_ms,
                "error": generated.error,
            },
            "context_budget": pack.budget,
            "validation": validation,
            "draft": draft,
        }

    async def validate_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        return validate_suite_draft(payload)

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
        validation = validate_suite_draft(cases_payload)
        if not validation["valid"]:
            summary = "; ".join(
                f"{item['path']}: {item['message']}" for item in validation["errors"][:10]
            )
            raise ValidationError("Invalid Evaluator Suite draft: " + summary)
        if target_type not in {"agent", "network"}:
            raise ValidationError("Evaluator Suite target_type must be agent or network")
        if authoring_source not in {"manual", "json_import", "ai_generated"}:
            raise ValidationError("Invalid authoring_source")
        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("Evaluator Suite name is required")
        dataset_name = f"{normalized_name} · Questions"
        now = datetime.now(timezone.utc)
        metadata = dict(authoring_metadata or {})

        async with self._session_factory() as session, session.begin():
            await self._provider_model(
                session,
                project_id=project_id,
                provider_model_id=judge_provider_model_id,
            )
            if authoring_source == "ai_generated":
                call_id = metadata.get("authoring_call_id")
                if not call_id:
                    raise ValidationError("AI-generated Suite requires authoring_call_id")
                try:
                    parsed_call_id = UUID(str(call_id))
                except (TypeError, ValueError) as exc:
                    raise ValidationError("authoring_call_id is invalid") from exc
                call = await session.get(EvaluationAuthoringCallModel, parsed_call_id)
                if (
                    call is None
                    or call.project_id != project_id
                    or call.status != "completed"
                ):
                    raise ValidationError(
                        "AI authoring call was not completed for this Project"
                    )
                if source_snapshot_hash != call.target_snapshot_hash:
                    raise ValidationError(
                        "Suite source_snapshot_hash does not match its authoring call"
                    )
                if source_context_hash != call.context_hash:
                    raise ValidationError(
                        "Suite source_context_hash does not match its authoring call"
                    )
                metadata.update(
                    {
                        "authoring_call_id": str(call.id),
                        "generator_provider_model_id": str(
                            call.generator_provider_model_id
                        ),
                        "generator_model": call.model,
                        "generator_provider": call.provider,
                        "generator_prompt_version": call.prompt_version,
                        "generation_input_tokens": call.input_tokens,
                        "generation_output_tokens": call.output_tokens,
                        "generation_cost_usd": (
                            float(call.cost_usd) if call.cost_usd is not None else None
                        ),
                    }
                )

            existing_suite = await session.scalar(
                select(EvaluationSuiteModel).where(
                    EvaluationSuiteModel.project_id == project_id,
                    func.lower(func.btrim(EvaluationSuiteModel.name))
                    == normalized_name.lower(),
                )
            )
            if existing_suite is not None:
                raise ConflictError("An Evaluation Suite with this name already exists")
            existing_dataset = await session.scalar(
                select(EvaluationDatasetModel).where(
                    EvaluationDatasetModel.project_id == project_id,
                    func.lower(func.btrim(EvaluationDatasetModel.name))
                    == dataset_name.lower(),
                )
            )
            if existing_dataset is not None:
                raise ConflictError(
                    "An internal Evaluation Dataset with this name already exists"
                )

            dataset = EvaluationDatasetModel(
                project_id=project_id,
                name=dataset_name,
                description=(
                    description.strip()
                    or f"Question set managed by {normalized_name}"
                ),
                status="active",
                created_by=created_by,
            )
            session.add(dataset)
            await session.flush()
            cases = validation["cases"]
            dataset_version = EvaluationDatasetVersionModel(
                dataset_id=dataset.id,
                project_id=project_id,
                version="v1",
                content_hash=canonical_hash(cases),
                change_description="Initial Evaluator Suite question set",
                authoring_source=authoring_source,
                source_snapshot_hash=source_snapshot_hash,
                source_context_hash=source_context_hash,
                authoring_metadata={
                    **metadata,
                    "validation": {
                        "warnings": validation["warnings"],
                        "coverage": validation["coverage"],
                    },
                },
                reviewed_at=now,
                reviewed_by=created_by,
                created_by=created_by,
            )
            session.add(dataset_version)
            await session.flush()
            session.add_all(
                [
                    EvaluationTestCaseModel(
                        dataset_version_id=dataset_version.id,
                        project_id=project_id,
                        position=index,
                        name=item["name"],
                        case_type=item["case_type"],
                        input_payload=item["input_payload"],
                        initial_context=item["initial_context"],
                        expected_contract=item["expected_contract"],
                        severity=item["severity"],
                        weight=item["weight"],
                        blocking=item["blocking"],
                        tags=item["tags"],
                        production_frequency=item["production_frequency"],
                    )
                    for index, item in enumerate(cases, start=1)
                ]
            )
            dataset.current_version_id = dataset_version.id

            suite = EvaluationSuiteModel(
                project_id=project_id,
                name=normalized_name,
                description=description.strip(),
                target_type=target_type,
                status="active",
                created_by=created_by,
            )
            session.add(suite)
            await session.flush()
            requested_output = int(judge_config.get("max_tokens", 800))
            requested_input = int(judge_config.get("maximum_input_tokens", 8000))
            normalized_judge_config = {
                **judge_config,
                "temperature": max(
                    0.0, min(float(judge_config.get("temperature", 0)), 1.0)
                ),
                "max_tokens": max(256, min(requested_output, 1200)),
                "timeout_seconds": max(
                    10.0,
                    min(float(judge_config.get("timeout_seconds", 90)), 180.0),
                ),
                "maximum_input_tokens": max(2000, min(requested_input, 32_000)),
            }
            suite_version = EvaluationSuiteVersionModel(
                suite_id=suite.id,
                project_id=project_id,
                version="v1",
                dataset_version_id=dataset_version.id,
                judge_provider_model_id=judge_provider_model_id,
                judge_config=normalized_judge_config,
                rubric=rubric,
                deterministic_checks=deterministic_checks,
                acceptance_policy=acceptance_policy,
                repetition_policy=repetition_policy,
                estimate_defaults=estimate_defaults,
                suite_hash=canonical_hash(
                    {
                        "dataset_version_id": str(dataset_version.id),
                        "judge_provider_model_id": str(judge_provider_model_id),
                        "judge_config": normalized_judge_config,
                        "rubric": rubric,
                        "deterministic_checks": deterministic_checks,
                        "acceptance_policy": acceptance_policy,
                        "repetition_policy": repetition_policy,
                        "estimate_defaults": estimate_defaults,
                    }
                ),
                created_by=created_by,
            )
            session.add(suite_version)
            await session.flush()
            suite.current_version_id = suite_version.id
            await session.flush()
            return {
                "id": str(suite.id),
                "project_id": str(project_id),
                "name": suite.name,
                "description": suite.description,
                "target_type": suite.target_type,
                "status": suite.status,
                "current_version_id": str(suite_version.id),
                "current_version": suite_version.version,
                "dataset_id": str(dataset.id),
                "dataset_version_id": str(dataset_version.id),
                "case_count": len(cases),
                "judge_provider_model_id": str(judge_provider_model_id),
                "judge_config": normalized_judge_config,
                "rubric": rubric,
                "deterministic_checks": deterministic_checks,
                "acceptance_policy": acceptance_policy,
                "repetition_policy": repetition_policy,
                "estimate_defaults": estimate_defaults,
                "suite_hash": suite_version.suite_hash,
                "authoring_source": authoring_source,
                "source_snapshot_hash": source_snapshot_hash,
                "source_context_hash": source_context_hash,
                "authoring_metadata": dataset_version.authoring_metadata,
                "reviewed_at": dataset_version.reviewed_at,
                "created_at": suite.created_at,
                "updated_at": suite.updated_at,
            }

    @staticmethod
    def _validate_case_count(case_count: int) -> int:
        value = int(case_count)
        if value < 5 or value > 50:
            raise ValidationError(
                "AI Suite generation supports between 5 and 50 Test Cases"
            )
        return value

    @staticmethod
    async def _provider_model(
        session,
        *,
        project_id: UUID,
        provider_model_id: UUID,
    ) -> ProviderModelModel:
        model = await session.get(ProviderModelModel, provider_model_id)
        if model is None or model.project_id != project_id or model.status != "active":
            raise NotFoundError("Provider Model not found or inactive")
        return model

    @staticmethod
    async def _provider_credential(
        session,
        *,
        project_id: UUID,
        credential_id: UUID,
    ) -> ProviderCredentialModel:
        credential = await session.get(ProviderCredentialModel, credential_id)
        if (
            credential is None
            or credential.project_id != project_id
            or credential.status != "active"
        ):
            raise NotFoundError("Provider Credential not found or inactive")
        return credential


__all__ = ["EvaluationSuiteAuthoringService"]
