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
    routing_key = record.event_type.replace(".", ".")
    body = json.dumps({
        "event_type": record.event_type,
        "event_version": record.event_version,
        "aggregate_type": record.aggregate_type,
        "aggregate_id": str(record.aggregate_id),
        "payload": record.payload,
        "correlation_id": str(record.correlation_id) if record.correlation_id else None,
        "causation_id": str(record.causation_id) if record.causation_id else None,
    })
    return RabbitMQMessageEnvelope(
        routing_key=routing_key,
        body=body,
        correlation_id=str(record.correlation_id) if record.correlation_id else "",
        headers={"event_type": record.event_type, "event_version": str(record.event_version)},
    )


def rabbit_message_to_inbox(message: Any) -> InboxEventModel:
    body = json.loads(message.body.decode())
    event_type = body.get("event_type", "")
    event_version = body.get("event_version", 1)
    routing_key = body.get("routing_key", message.routing_key or "")
    idempotency_key = body.get("idempotency_key", "")
    correlation_id_str = body.get("correlation_id")
    correlation_id = UUID(correlation_id_str) if correlation_id_str else uuid6.uuid7()
    causation_id_str = body.get("causation_id")
    causation_id = UUID(causation_id_str) if causation_id_str else None
    message_id = message.message_id or str(uuid6.uuid7())
    producer_module = body.get("producer_module", "agent")
    now = datetime.now(timezone.utc)

    return InboxEventModel(
        message_id=message_id,
        producer_module=producer_module,
        consumer_module="observability",
        outbox_origin_id=body.get("event_id"),
        aggregate_type="agent",
        event_type=event_type,
        event_version=event_version,
        routing_key=routing_key,
        payload=body.get("payload", {}),
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
