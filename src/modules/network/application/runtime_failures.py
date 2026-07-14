from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class NetworkRuntimeFailure(RuntimeError):
    """Safe, structured failure propagated from an Agent Run to its Network Run."""

    code: str
    stage: str
    safe_message: str
    internal_detail: str
    retryable: bool = False
    invocation_id: UUID | None = None
    node_id: UUID | None = None
    agent_id: UUID | None = None

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.internal_detail)

    def with_run_context(
        self,
        *,
        invocation_id: UUID,
        node_id: UUID,
        agent_id: UUID,
    ) -> NetworkRuntimeFailure:
        return replace(
            self,
            invocation_id=invocation_id,
            node_id=node_id,
            agent_id=agent_id,
        )

    def public_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "stage": self.stage,
            "message": self.safe_message,
            "retryable": self.retryable,
            "cause_invocation_id": str(self.invocation_id)
            if self.invocation_id
            else None,
            "cause_node_id": str(self.node_id) if self.node_id else None,
            "cause_agent_id": str(self.agent_id) if self.agent_id else None,
        }


def classify_runtime_exception(
    exception: Exception,
    *,
    stage: str = "agent_runtime",
) -> NetworkRuntimeFailure:
    if isinstance(exception, NetworkRuntimeFailure):
        return exception

    detail = str(exception) or exception.__class__.__name__
    normalized = f"{exception.__class__.__name__} {detail}".lower()

    if "credential" in normalized or "decrypt" in normalized or "secret" in normalized:
        return NetworkRuntimeFailure(
            code="credential_error",
            stage="credential_resolution",
            safe_message="The Agent provider credential could not be loaded.",
            internal_detail=detail,
            retryable=False,
        )
    if (
        "provider model" in normalized
        or "modelconfig" in normalized
        or "model binding" in normalized
    ):
        return NetworkRuntimeFailure(
            code="model_binding_error",
            stage="model_resolution",
            safe_message="The Agent provider model binding is not ready.",
            internal_detail=detail,
            retryable=False,
        )
    if (
        "base_url" in normalized
        or "settings" in normalized
        or "validationerror" in normalized
    ):
        return NetworkRuntimeFailure(
            code="runtime_configuration_error",
            stage="agent_bootstrap",
            safe_message="The Agent runtime configuration could not be loaded.",
            internal_detail=detail,
            retryable=False,
        )
    if "429" in normalized or "rate limit" in normalized:
        return NetworkRuntimeFailure(
            code="provider_rate_limited",
            stage="provider_request",
            safe_message="The model provider rate-limited this Agent Run.",
            internal_detail=detail,
            retryable=True,
        )
    if "timeout" in normalized or "timed out" in normalized:
        return NetworkRuntimeFailure(
            code="provider_timeout",
            stage="provider_request",
            safe_message="The model provider did not answer before the timeout.",
            internal_detail=detail,
            retryable=True,
        )

    return NetworkRuntimeFailure(
        code="agent_runtime_error",
        stage=stage,
        safe_message="The Agent Run failed before producing a valid result.",
        internal_detail=detail,
        retryable=False,
    )
