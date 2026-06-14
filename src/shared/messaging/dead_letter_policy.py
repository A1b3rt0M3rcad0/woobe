"""Standardized dead letter policy.

Defines dead-letter exchange (DLX) and dead-letter queue (DLQ) conventions
for all operational queues.

Rules:
1. Every operational queue must have a DLX and a DLQ with suffix '.dlq'.
2. Messages rejected for permanent errors or retry exhaustion go to the DLQ
   with error headers.
3. DLQ does not replace Inbox 'dead' status; both must allow audit.
4. Dead-lettered messages must preserve the original payload, routing_key,
   and producer metadata for audit purposes.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


DLQ_SUFFIX: str = ".dlq"
DLX_SUFFIX: str = ".dlx"


class DeadLetterReason(str, enum.Enum):
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    PERMANENT_ERROR = "permanent_error"
    INCOMPATIBLE_VERSION = "incompatible_version"
    INVALID_SCHEMA = "invalid_schema"
    REJECTED_BY_POLICY = "rejected_by_policy"


DEAD_LETTER_HEADER_PREFIX: str = "x-death"

REQUIRED_DEAD_LETTER_HEADERS: frozenset[str] = frozenset(
    [
        f"{DEAD_LETTER_HEADER_PREFIX}-reason",
        f"{DEAD_LETTER_HEADER_PREFIX}-original-routing-key",
        f"{DEAD_LETTER_HEADER_PREFIX}-original-producer-module",
        f"{DEAD_LETTER_HEADER_PREFIX}-attempts",
        f"{DEAD_LETTER_HEADER_PREFIX}-timestamp",
        f"{DEAD_LETTER_HEADER_PREFIX}-error",
    ]
)


def compute_dlq_name(queue_name: str) -> str:
    if not queue_name:
        raise ValueError("queue_name must not be empty")
    return f"{queue_name}{DLQ_SUFFIX}"


def compute_dlx_name(exchange_name: str) -> str:
    if not exchange_name:
        raise ValueError("exchange_name must not be empty")
    return f"{exchange_name}{DLX_SUFFIX}"


def dead_letter_headers(
    reason: DeadLetterReason,
    original_routing_key: str,
    original_producer_module: str,
    attempts: int,
    error: str,
) -> dict[str, str]:
    return {
        f"{DEAD_LETTER_HEADER_PREFIX}-reason": reason.value,
        f"{DEAD_LETTER_HEADER_PREFIX}-original-routing-key": original_routing_key,
        f"{DEAD_LETTER_HEADER_PREFIX}-original-producer-module": original_producer_module,
        f"{DEAD_LETTER_HEADER_PREFIX}-attempts": str(attempts),
        f"{DEAD_LETTER_HEADER_PREFIX}-timestamp": datetime.now(timezone.utc).isoformat(),
        f"{DEAD_LETTER_HEADER_PREFIX}-error": error,
    }


@dataclass
class DeadLetterRecord:
    reason: DeadLetterReason
    original_routing_key: str
    original_producer_module: str
    original_payload: dict[str, Any] = field(default_factory=dict)
    attempts: int = 0
    error: str = ""
    headers: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


def create_dead_letter_record(
    reason: DeadLetterReason,
    original_routing_key: str,
    original_producer_module: str,
    original_payload: dict[str, Any] | None = None,
    attempts: int = 0,
    error: str = "",
) -> DeadLetterRecord:
    headers = dead_letter_headers(
        reason=reason,
        original_routing_key=original_routing_key,
        original_producer_module=original_producer_module,
        attempts=attempts,
        error=error,
    )
    return DeadLetterRecord(
        reason=reason,
        original_routing_key=original_routing_key,
        original_producer_module=original_producer_module,
        original_payload=original_payload or {},
        attempts=attempts,
        error=error,
        headers=headers,
    )


def verify_dlq_headers(headers: dict[str, str]) -> bool:
    return REQUIRED_DEAD_LETTER_HEADERS.issubset(set(headers.keys()))


def is_dead_letter_queue_name(queue_name: str) -> bool:
    return queue_name.endswith(DLQ_SUFFIX)


def is_dead_letter_exchange_name(exchange_name: str) -> bool:
    return exchange_name.endswith(DLX_SUFFIX)
