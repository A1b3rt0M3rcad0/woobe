from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import uuid6

from modules.observability.infra.database.models import InboxEventModel, OutboxEventModel


@dataclass(frozen=True)
class RabbitMQMessageEnvelope:
    routing_key: str
    body: str
    correlation_id: str
    headers: dict[str, Any] = field(default_factory=dict)


def outbox_to_rabbit_message(record: OutboxEventModel) -> RabbitMQMessageEnvelope:
    routing_key = record.routing_key or record.event_type
    body = json.dumps(
        {
            "event_id": str(record.id),
            "event_type": record.event_type,
            "event_version": record.event_version,
            "producer_module": "observability",
            "routing_key": routing_key,
            "aggregate_type": record.aggregate_type,
            "aggregate_id": str(record.aggregate_id),
            "payload": record.payload,
            "idempotency_key": record.idempotency_key,
            "correlation_id": str(record.correlation_id) if record.correlation_id else None,
            "causation_id": str(record.causation_id) if record.causation_id else None,
        }
    )
    return RabbitMQMessageEnvelope(
        routing_key=routing_key,
        body=body,
        correlation_id=str(record.correlation_id) if record.correlation_id else "",
        headers={
            "event_type": record.event_type,
            "event_version": str(record.event_version),
            "idempotency_key": record.idempotency_key,
        },
    )


def _required_text(body: dict[str, Any], field: str) -> str:
    value = body.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Integration event requires {field}")
    return value


def rabbit_message_to_inbox(message: Any) -> InboxEventModel:
    body = json.loads(message.body.decode())
    event_id = UUID(_required_text(body, "event_id"))
    event_type = _required_text(body, "event_type")
    event_version = int(body.get("event_version", 1))
    routing_key = body.get("routing_key") or message.routing_key
    if not isinstance(routing_key, str) or not routing_key:
        raise ValueError("Integration event requires routing_key")
    idempotency_key = _required_text(body, "idempotency_key")

    correlation_id_raw = body.get("correlation_id")
    correlation_id = UUID(correlation_id_raw) if correlation_id_raw else uuid6.uuid7()
    causation_id_raw = body.get("causation_id")
    causation_id = UUID(causation_id_raw) if causation_id_raw else None
    message_id = message.message_id or str(event_id)
    payload = body.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Integration event payload must be an object")
    now = datetime.now(timezone.utc)

    return InboxEventModel(
        message_id=str(message_id),
        producer_module=str(body.get("producer_module") or "agent"),
        consumer_module="observability",
        outbox_origin_id=event_id,
        aggregate_type=str(body.get("aggregate_type") or "agent"),
        event_type=event_type,
        event_version=event_version,
        routing_key=routing_key,
        payload=payload,
        headers=dict(message.headers) if message.headers else None,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        causation_id=causation_id,
        status="received",
        attempts=0,
        available_at=now,
        created_at=now,
        updated_at=now,
    )
