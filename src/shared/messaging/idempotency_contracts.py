"""Standardized event idempotency contracts.

Every event published via Outbox must have a deterministic idempotency_key.
Duplicate delivery must not produce duplicate state changes.

Rules:
1. idempotency_key must be deterministic per command/event when possible.
2. Outbox and Inbox must have unique constraints on idempotency_key.
3. Handlers must be safe against reprocessing.
4. Duplicates must result in 'processed' or 'ignored', never a second state change.
"""
from __future__ import annotations

from typing import Any


IDEMPOTENCY_KEY_MIN_LENGTH: int = 1
IDEMPOTENCY_KEY_MAX_LENGTH: int = 255

IDEMPOTENCY_KEY_PATTERN: str = (
    "A deterministic hash or composite key derived from the immutable inputs "
    "of the event (e.g. aggregate_id, event_type, discriminator). "
    "Must be stable across retries of the same logical operation."
)


class IdempotencyKeyValidationError(ValueError):
    pass


def validate_idempotency_key(key: str) -> None:
    if not key or not isinstance(key, str):
        raise IdempotencyKeyValidationError(
            "idempotency_key must be a non-empty string"
        )
    if len(key) < IDEMPOTENCY_KEY_MIN_LENGTH:
        raise IdempotencyKeyValidationError(
            "idempotency_key must not be empty"
        )
    if len(key) > IDEMPOTENCY_KEY_MAX_LENGTH:
        raise IdempotencyKeyValidationError(
            f"idempotency_key exceeds maximum length of "
            f"{IDEMPOTENCY_KEY_MAX_LENGTH}: {len(key)}"
        )


def assert_idempotency_constraints(model_class: type[Any]) -> None:
    """Verify that the model class has idempotency unique constraints.

    Checks __table_args__ for UniqueConstraint entries related to
    idempotency_key or message_id.
    """
    from sqlalchemy import UniqueConstraint

    constraints: list[Any] = []
    table_args = getattr(model_class, "__table_args__", None)
    if table_args is None:
        raise IdempotencyKeyValidationError(
            f"{model_class.__name__} has no __table_args__"
        )
    if isinstance(table_args, tuple):
        constraints = [c for c in table_args if isinstance(c, UniqueConstraint)]
    has_idempotency = any(
        hasattr(c, "columns")
        and any(
            col.name in ("idempotency_key", "message_id")
            for col in c.columns
        )
        for c in constraints
    )
    if not has_idempotency:
        raise IdempotencyKeyValidationError(
            f"{model_class.__name__} must have a UniqueConstraint on "
            f"'idempotency_key' or 'message_id'"
        )


DUPLICATE_OUTCOMES: frozenset[str] = frozenset(
    [
        "processed",
        "ignored",
    ]
)

DUPLICATE_OUTBOX_OUTCOMES: frozenset[str] = frozenset(
    [
        "published",
        "duplicate",
    ]
)


def is_allowed_duplicate_outcome(status: str) -> bool:
    return status in DUPLICATE_OUTCOMES


def is_allowed_duplicate_outbox_outcome(status: str) -> bool:
    return status in DUPLICATE_OUTBOX_OUTCOMES
