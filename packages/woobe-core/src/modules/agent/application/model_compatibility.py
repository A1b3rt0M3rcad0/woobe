from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.agent.domain.model_spec import (
    ModelCapabilityNames,
    ModelSpec,
)


class CompatibilityMode:
    REQUIRED = "required"
    OPTIONAL = "optional"
    UNSUPPORTED = "unsupported"

    @classmethod
    def validate(cls, value: str, *, field_name: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in {
            cls.REQUIRED,
            cls.OPTIONAL,
            cls.UNSUPPORTED,
        }:
            raise ValueError(
                f"{field_name} must be required, optional or unsupported"
            )
        return normalized


@dataclass(frozen=True, slots=True)
class ExecutionStrategySpec:
    """Semantic requirements for one ExecutionStrategy algorithm."""

    name: str
    operations: frozenset[str]
    requires_conversation: bool = False
    allowed_input_modalities: frozenset[str] | None = None
    allowed_output_modalities: frozenset[str] | None = None
    required_capabilities: frozenset[str] = frozenset()
    context_mode: str = CompatibilityMode.OPTIONAL
    knowledge_mode: str = CompatibilityMode.OPTIONAL
    tools_mode: str = CompatibilityMode.OPTIONAL

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Execution Strategy spec name must not be empty")
        if not self.operations:
            raise ValueError(
                "Execution Strategy spec must support at least one Model operation"
            )
        object.__setattr__(
            self,
            "context_mode",
            CompatibilityMode.validate(
                self.context_mode,
                field_name="context_mode",
            ),
        )
        object.__setattr__(
            self,
            "knowledge_mode",
            CompatibilityMode.validate(
                self.knowledge_mode,
                field_name="knowledge_mode",
            ),
        )
        object.__setattr__(
            self,
            "tools_mode",
            CompatibilityMode.validate(
                self.tools_mode,
                field_name="tools_mode",
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "operations": sorted(self.operations),
            "requires_conversation": self.requires_conversation,
            "allowed_input_modalities": (
                sorted(self.allowed_input_modalities)
                if self.allowed_input_modalities is not None
                else None
            ),
            "allowed_output_modalities": (
                sorted(self.allowed_output_modalities)
                if self.allowed_output_modalities is not None
                else None
            ),
            "required_capabilities": sorted(self.required_capabilities),
            "context_mode": self.context_mode,
            "knowledge_mode": self.knowledge_mode,
            "tools_mode": self.tools_mode,
        }


@dataclass(frozen=True, slots=True)
class CompatibilityIssue:
    code: str
    component: str
    requirement: str
    actual: Any
    severity: str = "error"

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "component": self.component,
            "requirement": self.requirement,
            "actual": self.actual,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    issues: tuple[CompatibilityIssue, ...] = ()

    @property
    def compatible(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def errors(self) -> tuple[CompatibilityIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity == "error"
        )

    @property
    def warnings(self) -> tuple[CompatibilityIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity == "warning"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "compatible": self.compatible,
            "issues": [issue.as_dict() for issue in self.issues],
        }


@dataclass(frozen=True, slots=True)
class RuntimeCompatibilityRequest:
    model: ModelSpec
    execution: ExecutionStrategySpec
    tools_enabled: bool = False
    context_enabled: bool = False
    knowledge_enabled: bool = False
    required_input_modalities: frozenset[str] = frozenset()
    required_output_modalities: frozenset[str] = frozenset()


class ModelExecutionCompatibilityResolver:
    """Validate a complete runtime composition before provider invocation."""

    def resolve(
        self,
        request: RuntimeCompatibilityRequest,
    ) -> CompatibilityReport:
        issues: list[CompatibilityIssue] = []
        model = request.model
        execution = request.execution

        if not (model.operations & execution.operations):
            issues.append(
                CompatibilityIssue(
                    code="operation_not_supported",
                    component="execution_strategy",
                    requirement="one of " + ", ".join(sorted(execution.operations)),
                    actual=sorted(model.operations),
                )
            )

        if (
            execution.requires_conversation
            and not model.interaction.supports_conversation
        ):
            issues.append(
                CompatibilityIssue(
                    code="conversation_not_supported",
                    component="model",
                    requirement="conversational interaction",
                    actual=model.interaction.mode,
                )
            )

        if execution.allowed_input_modalities is not None:
            unsupported = (
                model.input_modalities - execution.allowed_input_modalities
            )
            if unsupported:
                issues.append(
                    CompatibilityIssue(
                        code="execution_input_modality_not_supported",
                        component="execution_strategy",
                        requirement=sorted(execution.allowed_input_modalities),
                        actual=sorted(model.input_modalities),
                    )
                )

        if execution.allowed_output_modalities is not None:
            if not (
                model.output_modalities
                & execution.allowed_output_modalities
            ):
                issues.append(
                    CompatibilityIssue(
                        code="execution_output_modality_not_supported",
                        component="execution_strategy",
                        requirement=sorted(execution.allowed_output_modalities),
                        actual=sorted(model.output_modalities),
                    )
                )

        for modality in request.required_input_modalities:
            if not model.accepts(modality):
                issues.append(
                    CompatibilityIssue(
                        code="model_input_modality_not_supported",
                        component="model",
                        requirement=modality,
                        actual=sorted(model.input_modalities),
                    )
                )

        for modality in request.required_output_modalities:
            if not model.produces(modality):
                issues.append(
                    CompatibilityIssue(
                        code="model_output_modality_not_supported",
                        component="model",
                        requirement=modality,
                        actual=sorted(model.output_modalities),
                    )
                )

        self._component_mode_issue(
            issues,
            component="context",
            mode=execution.context_mode,
            enabled=request.context_enabled,
        )
        self._component_mode_issue(
            issues,
            component="knowledge",
            mode=execution.knowledge_mode,
            enabled=request.knowledge_enabled,
        )
        self._component_mode_issue(
            issues,
            component="tools",
            mode=execution.tools_mode,
            enabled=request.tools_enabled,
        )

        for capability_name in execution.required_capabilities:
            self._require_model_capability(
                issues,
                model=model,
                capability_name=capability_name,
                component="execution_strategy",
            )

        if request.tools_enabled:
            self._require_model_capability(
                issues,
                model=model,
                capability_name=ModelCapabilityNames.TOOL_CALLING,
                component="tools",
            )

        return CompatibilityReport(tuple(issues))

    @staticmethod
    def _component_mode_issue(
        issues: list[CompatibilityIssue],
        *,
        component: str,
        mode: str,
        enabled: bool,
    ) -> None:
        if mode == CompatibilityMode.REQUIRED and not enabled:
            issues.append(
                CompatibilityIssue(
                    code=f"{component}_required",
                    component=component,
                    requirement="enabled",
                    actual="disabled",
                )
            )
        elif mode == CompatibilityMode.UNSUPPORTED and enabled:
            issues.append(
                CompatibilityIssue(
                    code=f"{component}_not_supported",
                    component=component,
                    requirement="disabled",
                    actual="enabled",
                )
            )

    @staticmethod
    def _require_model_capability(
        issues: list[CompatibilityIssue],
        *,
        model: ModelSpec,
        capability_name: str,
        component: str,
    ) -> None:
        capability = model.capability(capability_name)
        if capability is not None and capability.supported:
            return

        # Existing ProviderModels may predate explicit capability metadata. Preserve
        # current behavior during migration but surface the uncertainty. New normalized
        # specs fail closed when a required capability is absent.
        if capability is None and model.source == "legacy":
            issues.append(
                CompatibilityIssue(
                    code="model_capability_unknown",
                    component=component,
                    requirement=capability_name,
                    actual=None,
                    severity="warning",
                )
            )
            return

        issues.append(
            CompatibilityIssue(
                code="model_capability_not_supported",
                component=component,
                requirement=capability_name,
                actual=(
                    capability.supported
                    if capability is not None
                    else None
                ),
            )
        )


__all__ = [
    "CompatibilityIssue",
    "CompatibilityMode",
    "CompatibilityReport",
    "ExecutionStrategySpec",
    "ModelExecutionCompatibilityResolver",
    "RuntimeCompatibilityRequest",
]
