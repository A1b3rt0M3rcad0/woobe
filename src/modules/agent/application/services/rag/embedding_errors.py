from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EmbeddingFailure:
    category: str
    safe_message: str
    upstream_status: int | None = None
    upstream_error_code: str | None = None
    retryable: bool = False


class EmbeddingProviderError(RuntimeError):
    """Safe, structured embedding failure for build and runtime RAG flows."""

    def __init__(self, failure: EmbeddingFailure) -> None:
        self.failure = failure
        super().__init__(failure.safe_message)

    @property
    def upstream_status(self) -> int | None:
        return self.failure.upstream_status

    @property
    def upstream_error_code(self) -> str | None:
        return self.failure.upstream_error_code

    @property
    def retryable(self) -> bool:
        return self.failure.retryable

    @property
    def category(self) -> str:
        return self.failure.category


def _status_code(exc: Exception) -> int | None:
    candidates = [
        getattr(exc, "status_code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
    ]
    for value in candidates:
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue

    match = re.search(r"(?:error\s+code|status(?:\s+code)?)\s*[:=]?\s*(\d{3})", str(exc), re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _error_code(value: Any) -> str | None:
    if isinstance(value, dict):
        nested = value.get("error")
        if isinstance(nested, dict):
            nested_code = nested.get("code") or nested.get("type")
            if nested_code is not None:
                return str(nested_code)
        direct = value.get("code") or value.get("type")
        if direct is not None:
            return str(direct)
    return None


def _upstream_error_code(exc: Exception) -> str | None:
    for value in (
        getattr(exc, "body", None),
        getattr(exc, "error", None),
        getattr(exc, "response", None),
    ):
        code = _error_code(value)
        if code:
            return code

    text = str(exc).lower()
    if "insufficient credit" in text or "insufficient balance" in text:
        return "insufficient_credits"
    if "rate limit" in text:
        return "rate_limit"
    if "unauthorized" in text or "invalid api key" in text:
        return "invalid_credential"
    return None


def normalize_embedding_error(exc: Exception) -> EmbeddingFailure:
    if isinstance(exc, EmbeddingProviderError):
        return exc.failure

    status = _status_code(exc)
    code = _upstream_error_code(exc)
    text = str(exc).lower()

    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "timed out" in text or "timeout" in text:
        return EmbeddingFailure(
            category="provider_timeout",
            safe_message="Embedding provider request timed out.",
            upstream_status=status,
            upstream_error_code=code or "timeout",
            retryable=True,
        )

    if status == 401:
        return EmbeddingFailure(
            category="provider_authentication",
            safe_message="Embedding provider rejected the configured credential.",
            upstream_status=status,
            upstream_error_code=code or "unauthorized",
        )
    if status == 402 or "insufficient credit" in text or "insufficient balance" in text:
        return EmbeddingFailure(
            category="provider_billing",
            safe_message="Embedding provider account has insufficient credits.",
            upstream_status=status or 402,
            upstream_error_code=code or "insufficient_credits",
        )
    if status == 403:
        return EmbeddingFailure(
            category="provider_authorization",
            safe_message="Embedding provider denied access to the configured embedding model.",
            upstream_status=status,
            upstream_error_code=code or "forbidden",
        )
    if status == 404:
        return EmbeddingFailure(
            category="model_not_found",
            safe_message="Embedding model was not found by the provider.",
            upstream_status=status,
            upstream_error_code=code or "model_not_found",
        )
    if status == 429 or "rate limit" in text:
        return EmbeddingFailure(
            category="provider_rate_limit",
            safe_message="Embedding provider rate limit was reached. Try again later.",
            upstream_status=status or 429,
            upstream_error_code=code or "rate_limit",
            retryable=True,
        )
    if status is not None and status >= 500:
        return EmbeddingFailure(
            category="provider_unavailable",
            safe_message="Embedding provider is temporarily unavailable.",
            upstream_status=status,
            upstream_error_code=code or "provider_unavailable",
            retryable=True,
        )
    if status == 400:
        return EmbeddingFailure(
            category="invalid_embedding_request",
            safe_message="Embedding provider rejected the request. Check the embedding model configuration.",
            upstream_status=status,
            upstream_error_code=code or "invalid_request",
        )
    if "not supported for mvp" in text or "unsupported" in text:
        return EmbeddingFailure(
            category="unsupported_embedding_provider",
            safe_message="Configured embedding provider is not supported.",
            upstream_status=status,
            upstream_error_code=code or "unsupported_provider",
        )

    return EmbeddingFailure(
        category="provider_error",
        safe_message="Embedding provider request failed.",
        upstream_status=status,
        upstream_error_code=code,
        retryable=False,
    )


def as_embedding_provider_error(exc: Exception) -> EmbeddingProviderError:
    if isinstance(exc, EmbeddingProviderError):
        return exc
    return EmbeddingProviderError(normalize_embedding_error(exc))
