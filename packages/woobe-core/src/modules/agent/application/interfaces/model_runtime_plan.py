from __future__ import annotations

from dataclasses import dataclass

from modules.agent.application.interfaces.model_compatibility import (
    CompatibilityReport,
    ExecutionStrategySpec,
    ModelExecutionCompatibilityResolver,
    RuntimeCompatibilityRequest,
)
from modules.agent.domain.model_spec import ModelSpec


@dataclass(frozen=True, slots=True)
class ModelRuntimePlan:
    """Immutable semantic bindings for one model execution."""

    model: ModelSpec
    execution_strategy: str
    model_strategy: str
    output_strategy: str
    context_strategy: str | None = None
    knowledge_strategy: str | None = None
    tools_enabled: bool = False


class IncompatibleModelRuntimePlanError(ValueError):
    def __init__(self, report: CompatibilityReport) -> None:
        self.report = report
        details = "; ".join(
            f"{issue.code}: {issue.requirement}"
            for issue in report.errors
        )
        super().__init__(
            "Model runtime composition is incompatible"
            + (f": {details}" if details else "")
        )


class ModelRuntimePlanBuilder:
    __slots__ = ("_compatibility",)

    def __init__(
        self,
        compatibility: ModelExecutionCompatibilityResolver | None = None,
    ) -> None:
        self._compatibility = (
            compatibility or ModelExecutionCompatibilityResolver()
        )

    def build(
        self,
        *,
        model: ModelSpec,
        execution: ExecutionStrategySpec,
        model_strategy: str | None = None,
        context_strategy: str | None = None,
        knowledge_strategy: str | None = None,
        output_strategy: str,
        tools_enabled: bool = False,
        required_input_modalities: frozenset[str] = frozenset(),
        required_output_modalities: frozenset[str] = frozenset(),
    ) -> ModelRuntimePlan:
        resolved_model_strategy = (
            model_strategy
            or model.default_model_strategy
            or next(iter(sorted(model.operations)))
        )
        if resolved_model_strategy not in model.operations:
            raise ValueError(
                "Model operation strategy must match a ModelSpec operation: "
                f"{resolved_model_strategy}"
            )
        if not output_strategy.strip():
            raise ValueError("Output strategy must not be empty")

        report = self._compatibility.resolve(
            RuntimeCompatibilityRequest(
                model=model,
                execution=execution,
                tools_enabled=tools_enabled,
                context_enabled=context_strategy is not None,
                knowledge_enabled=knowledge_strategy is not None,
                required_input_modalities=required_input_modalities,
                required_output_modalities=required_output_modalities,
            )
        )
        if not report.compatible:
            raise IncompatibleModelRuntimePlanError(report)

        return ModelRuntimePlan(
            model=model,
            execution_strategy=execution.name,
            model_strategy=resolved_model_strategy,
            context_strategy=context_strategy,
            knowledge_strategy=knowledge_strategy,
            output_strategy=output_strategy,
            tools_enabled=tools_enabled,
        )


__all__ = [
    "IncompatibleModelRuntimePlanError",
    "ModelRuntimePlan",
    "ModelRuntimePlanBuilder",
]
