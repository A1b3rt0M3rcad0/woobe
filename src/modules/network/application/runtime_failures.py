from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterator
from uuid import UUID


@dataclass
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
    trace_id: UUID | None = None
    agent_session_id: UUID | None = None
    phase: str | None = None
    call_index: int | None = None
    upstream_status: int | None = None
    upstream_error_code: str | None = None
    partial_result_available: bool = False

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

    def with_agent_context(
        self,
        *,
        trace_id: UUID | None,
        agent_session_id: UUID | None,
    ) -> NetworkRuntimeFailure:
        return replace(
            self,
            trace_id=trace_id,
            agent_session_id=agent_session_id,
        )

    def public_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "stage": self.stage,
            "message": self.safe_message,
            "retryable": self.retryable,
            "phase": self.phase,
            "call_index": self.call_index,
            "upstream_status": self.upstream_status,
            "upstream_error_code": self.upstream_error_code,
            "partial_result_available": self.partial_result_available,
            "cause_invocation_id": str(self.invocation_id)
            if self.invocation_id
            else None,
            "cause_node_id": str(self.node_id) if self.node_id else None,
            "cause_agent_id": str(self.agent_id) if self.agent_id else None,
            "trace_id": str(self.trace_id) if self.trace_id else None,
            "agent_session_id": (
                str(self.agent_session_id) if self.agent_session_id else None
            ),
        }


def _failure_context(chain: list[Exception]) -> dict[str, Any]:
    for item in chain:
        value = getattr(item, "failure_context", None)
        if isinstance(value, dict):
            return value
    return {}


def _failure_fields(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "phase": context.get("phase") if isinstance(context.get("phase"), str) else None,
        "call_index": context.get("call_index") if isinstance(context.get("call_index"), int) else None,
        "upstream_status": context.get("upstream_status") if isinstance(context.get("upstream_status"), int) else None,
        "upstream_error_code": str(context["upstream_error_code"])
        if context.get("upstream_error_code")
        else None,
        "partial_result_available": context.get("partial_result_available") is True,
    }


def _provider_request_message(phase: str | None) -> str:
    if phase and phase.startswith("tool_followup_"):
        return "The model provider rejected a Tool follow-up request."
    if phase == "final_response_generation":
        return "The model provider rejected the final response request."
    return "The model provider rejected the Agent request."


def _instrumented_orchestration_failure(
    normalized: str,
    detail: str,
    fields: dict[str, Any],
) -> NetworkRuntimeFailure | None:
    """Classify local InstrumentedExecutionError values before provider mapping.

    InstrumentedExecutionError is an execution envelope, not proof that an upstream
    provider rejected a request. Provider failures still classify through their
    concrete exception/status signatures below.
    """

    if "instrumentedexecutionerror" not in normalized:
        return None
    if "repeated semantic tool failures" in normalized:
        return NetworkRuntimeFailure(
            code="repeated_tool_failures",
            stage="tool_orchestration",
            safe_message=(
                "The Agent stopped after repeated Tool or delegation failures."
            ),
            internal_detail=detail,
            retryable=False,
            **fields,
        )
    if "tool round limit" in normalized or "tool call round limit" in normalized:
        return NetworkRuntimeFailure(
            code="tool_loop_exhausted",
            stage="tool_orchestration",
            safe_message="The Agent reached the Tool orchestration round limit.",
            internal_detail=detail,
            retryable=False,
            **fields,
        )
    return None


def classify_runtime_exception(
    exception: Exception,
    *,
    stage: str = "agent_runtime",
) -> NetworkRuntimeFailure:
    if isinstance(exception, NetworkRuntimeFailure):
        return exception

    chain = list(_exception_chain(exception))
    detail = _internal_exception_detail(chain)
    context = _failure_context(chain)
    fields = _failure_fields(context)
    normalized = " ".join(
        f"{item.__class__.__module__}.{item.__class__.__name__} {str(item)}"
        for item in chain
    ).lower()

    if "credential" in normalized or "decrypt" in normalized or "secret" in normalized:
        return NetworkRuntimeFailure(
            code="credential_error",
            stage="credential_resolution",
            safe_message="The Agent provider credential could not be loaded.",
            internal_detail=detail,
            retryable=False,
            **fields,
        )
    if (
        "authenticationerror" in normalized
        or "permissiondeniederror" in normalized
        or "unauthorized" in normalized
        or "invalid api key" in normalized
        or "incorrect api key" in normalized
        or "status code: 401" in normalized
        or "error code: 401" in normalized
        or "status code: 403" in normalized
        or "error code: 403" in normalized
    ):
        return NetworkRuntimeFailure(
            code="provider_authentication_error",
            stage="provider_request",
            safe_message="The model provider rejected the configured authentication.",
            internal_detail=detail,
            retryable=False,
            **fields,
        )
    if (
        "provider model" in normalized
        or "modelconfig" in normalized
        or "model binding" in normalized
        or "model_not_found" in normalized
        or ("model" in normalized and "not found" in normalized)
    ):
        return NetworkRuntimeFailure(
            code="model_binding_error",
            stage="model_resolution",
            safe_message="The Agent provider model binding is not ready.",
            internal_detail=detail,
            retryable=False,
            **fields,
        )
    if (
        "base_url" in normalized
        or "settings" in normalized
        or "runtime session factory" in normalized
        or "http tool executor is not configured" in normalized
    ):
        return NetworkRuntimeFailure(
            code="runtime_configuration_error",
            stage="agent_bootstrap",
            safe_message="The Agent runtime configuration could not be loaded.",
            internal_detail=detail,
            retryable=False,
            **fields,
        )
    if (
        "knowledgeversion" in normalized
        or "knowledge version" in normalized
        or "vector snapshot" in normalized
        or "embedding provider" in normalized
    ):
        return NetworkRuntimeFailure(
            code="knowledge_binding_error",
            stage="knowledge_resolution",
            safe_message="The Agent knowledge binding is not ready for this Run.",
            internal_detail=detail,
            retryable=False,
            **fields,
        )
    if (
        "selected tool" in normalized
        or "tool snapshot" in normalized
        or "delegation tool name collides" in normalized
        or "tool runtime" in normalized
    ):
        return NetworkRuntimeFailure(
            code="tool_binding_error",
            stage="tool_resolution",
            safe_message="The Agent tool binding is not ready for this Run.",
            internal_detail=detail,
            retryable=False,
            **fields,
        )
    if "validationerror" in normalized:
        return NetworkRuntimeFailure(
            code="runtime_configuration_error",
            stage="agent_bootstrap",
            safe_message="The Agent runtime configuration could not be loaded.",
            internal_detail=detail,
            retryable=False,
            **fields,
        )
    if (
        "ratelimiterror" in normalized
        or "status code: 429" in normalized
        or "error code: 429" in normalized
        or "rate limit" in normalized
    ):
        return NetworkRuntimeFailure(
            code="provider_rate_limited",
            stage="provider_request",
            safe_message="The model provider rate-limited this Agent Run.",
            internal_detail=detail,
            retryable=True,
            **fields,
        )
    if (
        "apitimeouterror" in normalized
        or "readtimeout" in normalized
        or "connecttimeout" in normalized
        or "timeout" in normalized
        or "timed out" in normalized
    ):
        return NetworkRuntimeFailure(
            code="provider_timeout",
            stage="provider_request",
            safe_message="The model provider did not answer before the timeout.",
            internal_detail=detail,
            retryable=True,
            **fields,
        )
    if (
        "apiconnectionerror" in normalized
        or "connecterror" in normalized
        or "connection error" in normalized
        or "connection refused" in normalized
        or "name or service not known" in normalized
        or "name resolution" in normalized
        or "nodename nor servname" in normalized
    ):
        return NetworkRuntimeFailure(
            code="provider_unreachable",
            stage="provider_request",
            safe_message="The Agent worker could not reach the model provider.",
            internal_detail=detail,
            retryable=True,
            **fields,
        )
    if (
        "internalservererror" in normalized
        or "status code: 500" in normalized
        or "error code: 500" in normalized
        or "status code: 502" in normalized
        or "error code: 502" in normalized
        or "status code: 503" in normalized
        or "error code: 503" in normalized
        or "status code: 504" in normalized
        or "error code: 504" in normalized
    ):
        return NetworkRuntimeFailure(
            code="provider_unavailable",
            stage="provider_request",
            safe_message="The model provider is temporarily unavailable.",
            internal_detail=detail,
            retryable=True,
            **fields,
        )

    local_orchestration = _instrumented_orchestration_failure(
        normalized,
        detail,
        fields,
    )
    if local_orchestration is not None:
        return local_orchestration

    if (
        "apistatuserror" in normalized
        or "badrequesterror" in normalized
        or "openai.notfounderror" in normalized
        or "unprocessableentityerror" in normalized
        or "ai provider error" in normalized
        or "status code: 400" in normalized
        or "error code: 400" in normalized
        or "status code: 404" in normalized
        or "error code: 404" in normalized
        or "status code: 422" in normalized
        or "error code: 422" in normalized
    ):
        return NetworkRuntimeFailure(
            code="provider_request_error",
            stage="provider_request",
            safe_message=_provider_request_message(fields["phase"]),
            internal_detail=detail,
            retryable=False,
            **fields,
        )

    if "instrumentedexecutionerror" in normalized:
        return NetworkRuntimeFailure(
            code="agent_orchestration_error",
            stage="agent_orchestration",
            safe_message="The Agent orchestration could not complete a valid result.",
            internal_detail=detail,
            retryable=False,
            **fields,
        )

    return NetworkRuntimeFailure(
        code="agent_runtime_error",
        stage=stage,
        safe_message="The Agent Run failed before producing a valid result.",
        internal_detail=detail,
        retryable=False,
        **fields,
    )


def _exception_chain(exception: Exception) -> Iterator[Exception]:
    """Yield an exception and its explicit/implicit causes without looping."""
    current: BaseException | None = exception
    seen: set[int] = set()
    while isinstance(current, Exception) and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _internal_exception_detail(chain: list[Exception]) -> str:
    parts: list[str] = []
    for item in chain:
        name = item.__class__.__name__
        message = str(item).strip()
        part = f"{name}: {message}" if message else name
        if not parts or parts[-1] != part:
            parts.append(part)
    return " <- ".join(parts)
