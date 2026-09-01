"""Standardized event retry policy.

Defines transient vs permanent error classification and exponential backoff
with jitter for retryable events.

Rules:
1. Transient errors: network, broker unavailable, deadlock, timeout, DB connection.
2. Permanent errors: invalid schema, missing handler, incompatible payload,
   business rule that cannot be retried.
3. Backoff: exponential with jitter; available_at calculates next attempt.
4. max_attempts default: 5, configurable per module.
"""
from __future__ import annotations

import enum
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol


DEFAULT_MAX_ATTEMPTS: int = 5
DEFAULT_BASE_DELAY_SECONDS: float = 1.0
DEFAULT_MAX_DELAY_SECONDS: float = 300.0
DEFAULT_JITTER_FACTOR: float = 0.1


class RetryClassification(str, enum.Enum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"


TRANSIENT_ERROR_TYPES: frozenset[str] = frozenset(
    [
        "ConnectionError",
        "ConnectionRefusedError",
        "ConnectionResetError",
        "ConnectionAbortedError",
        "TimeoutError",
        "OperationalError",
        "DatabaseError",
        "DeadlockDetected",
        "ResourceBusy",
        "NetworkUnreachable",
        "BrokerUnavailable",
        "ServiceUnavailable",
    ]
)

PERMANENT_ERROR_TYPES: frozenset[str] = frozenset(
    [
        "ValidationError",
        "SchemaError",
        "IncompatibleVersionError",
        "InvalidPayloadError",
        "MissingHandlerError",
        "BusinessRuleViolation",
    ]
)

RETRYABLE_STATUSES: frozenset[str] = frozenset(
    [
        "retryable",
        "pending",
    ]
)

TERMINAL_STATUSES: frozenset[str] = frozenset(
    [
        "published",
        "processed",
        "dead",
        "ignored",
    ]
)


@dataclass
class RetryState:
    attempts: int = 0
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS
    last_error: str | None = None
    available_at: datetime | None = None


class HasRetryState(Protocol):
    @property
    def attempts(self) -> int: ...

    @property
    def status(self) -> str: ...


def classify_error(error: str) -> RetryClassification:
    for error_type in PERMANENT_ERROR_TYPES:
        if error_type.lower() in error.lower():
            return RetryClassification.PERMANENT
    for error_type in TRANSIENT_ERROR_TYPES:
        if error_type.lower() in error.lower():
            return RetryClassification.TRANSIENT
    return RetryClassification.TRANSIENT


def compute_backoff_delay(
    attempts: int,
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS,
    jitter_factor: float = DEFAULT_JITTER_FACTOR,
) -> float:
    if attempts < 1:
        attempts = 1
    exponential = base_delay_seconds * (2 ** (attempts - 1))
    capped = min(exponential, max_delay_seconds)
    jitter = capped * jitter_factor * (random.random() * 2 - 1)
    return max(0.0, capped + jitter)


def compute_next_available_at(
    attempts: int,
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS,
    jitter_factor: float = DEFAULT_JITTER_FACTOR,
) -> datetime:
    delay = compute_backoff_delay(
        attempts=attempts,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
        jitter_factor=jitter_factor,
    )
    return datetime.now(timezone.utc) + timedelta(seconds=delay)


def should_retry(
    attempts: int,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    classification: RetryClassification | None = None,
    error: str = "",
) -> bool:
    if classification is None:
        classification = classify_error(error)
    if classification == RetryClassification.PERMANENT:
        return False
    return attempts < max_attempts


def is_retryable_status(status: str) -> bool:
    return status in RETRYABLE_STATUSES


def is_terminal_status(status: str) -> bool:
    return status in TERMINAL_STATUSES
