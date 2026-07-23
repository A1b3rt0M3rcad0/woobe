from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.evaluation.application.compatible_resumable_authoring import (
    CompatibleResumableEvaluationSuiteAuthoringService,
)
from modules.evaluation.infra.database.models import EvaluationAuthoringCallModel
from shared.infra.errors import NotFoundError, ValidationError


class SessionAwareEvaluationSuiteAuthoringService(
    CompatibleResumableEvaluationSuiteAuthoringService
):
    """Add an explicit single-turn/session generation contract to Suite authoring."""

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
        test_structure: str = "single_turn",
        minimum_session_turns: int = 2,
        maximum_session_turns: int = 5,
    ) -> dict[str, Any]:
        structure = str(test_structure or "single_turn")
        if structure not in {"single_turn", "session", "mixed"}:
            raise ValidationError("Unsupported Evaluation test structure")
        minimum_turns = max(2, min(int(minimum_session_turns), 10))
        maximum_turns = max(2, min(int(maximum_session_turns), 20))
        if maximum_turns < minimum_turns:
            raise ValidationError(
                "maximum_session_turns must be greater than or equal to minimum_session_turns"
            )

        instruction = (
            "\n\nEvaluation interaction contract: "
            f"test_structure={structure}; session_turn_range={minimum_turns}-{maximum_turns}. "
            "single_turn cases must set interaction_mode=single_turn and turns=[]. "
            "session cases must set interaction_mode=session and contain a coherent ordered turns array; "
            "each turn must contain message, expected_behavior and forbidden_behavior. "
            "For mixed generation include both interaction modes."
        )
        created = await super().generate_draft(
            project_id=project_id,
            target=target,
            generator_provider_model_id=generator_provider_model_id,
            objective=objective.strip() + instruction,
            case_count=case_count,
            coverage=coverage,
            error_case_ratio=error_case_ratio,
            language=language,
            maximum_input_tokens=maximum_input_tokens,
            maximum_cost_usd=maximum_cost_usd,
            created_by=created_by,
        )
        call_id = UUID(str(created["authoring_call_id"]))
        async with self._session_factory() as session, session.begin():
            call = await session.get(
                EvaluationAuthoringCallModel,
                call_id,
                with_for_update=True,
            )
            if call is None or call.project_id != project_id:
                raise NotFoundError("Evaluation authoring call not found")
            call.objective = objective.strip()
            request = dict(call.coverage_request or {})
            request.update(
                {
                    "test_structure": structure,
                    "minimum_session_turns": minimum_turns,
                    "maximum_session_turns": maximum_turns,
                }
            )
            call.coverage_request = request
            context = dict(call.context_payload or {})
            context["evaluation_test_structure"] = {
                "mode": structure,
                "minimum_session_turns": minimum_turns,
                "maximum_session_turns": maximum_turns,
                "rules": [
                    "single_turn requires an empty turns array",
                    "session requires one isolated conversation per Trial repetition",
                    "session turns are ordered user messages judged together as one Session Test",
                ],
            }
            call.context_payload = context
        return await self.get_authoring_call(project_id, call_id)


__all__ = ["SessionAwareEvaluationSuiteAuthoringService"]
