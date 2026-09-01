from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from modules.identity.infra.database.models import InboxEventModel, OutboxEventModel


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
    return InboxEventModel(
        outbox_origin_id=body.get("aggregate_id"),
        aggregate_type=body.get("aggregate_type", ""),
        event_type=body.get("event_type", ""),
        event_version=body.get("event_version", 1),
        payload=body.get("payload", {}),
        correlation_id=body.get("correlation_id"),
        causation_id=body.get("causation_id"),
    )
