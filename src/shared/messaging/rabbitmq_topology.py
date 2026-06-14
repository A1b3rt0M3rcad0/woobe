"""Standardized RabbitMQ topology contracts.

Defines exchange, queue, binding, and publisher-confirm conventions
applicable to all modules.

Rules:
 1. Exchange: `domain.events`, type `topic`, durable, non-auto-delete.
 2. Queue naming: `<consumer_module>.<producer_module>-events`.
 3. Routing key: `<producer_module>.<domain_event>.v<version>`.
 4. Every operational queue has a DLQ with suffix `.dlq`.
 5. Publisher confirms are mandatory for every message published.
 6. Consumers must not ack before durable Inbox persistence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from shared.messaging.dead_letter_policy import compute_dlq_name


EXCHANGE_NAME: str = "domain.events"
EXCHANGE_TYPE: str = "topic"
EXCHANGE_DURABLE: bool = True
EXCHANGE_AUTO_DELETE: bool = False

QUEUE_NAME_PATTERN: re.Pattern[str] = re.compile(
    r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\-events$"
)

ROUTING_KEY_PATTERN: re.Pattern[str] = re.compile(
    r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\.v\d+$"
)

BINDING_PATTERN: re.Pattern[str] = re.compile(
    r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){2,}\.v\d+$"
)

QUEUE_GROUP_SUFFIX: str = "events"


class TopologyValidationError(ValueError):
    pass


@runtime_checkable
class PublisherConfirmsProtocol(Protocol):
    def publish(self, exchange: str, routing_key: str, body: bytes) -> bool: ...


def compute_queue_name(consumer_module: str, producer_module: str) -> str:
    if not consumer_module or not isinstance(consumer_module, str):
        raise TopologyValidationError(
            f"consumer_module must be a non-empty string, got: {consumer_module!r}"
        )
    if not producer_module or not isinstance(producer_module, str):
        raise TopologyValidationError(
            f"producer_module must be a non-empty string, got: {producer_module!r}"
        )
    if not re.match(r"^[a-z][a-z0-9_]*$", consumer_module):
        raise TopologyValidationError(
            f"consumer_module must match '^[a-z][a-z0-9_]*$', got: {consumer_module!r}"
        )
    if not re.match(r"^[a-z][a-z0-9_]*$", producer_module):
        raise TopologyValidationError(
            f"producer_module must match '^[a-z][a-z0-9_]*$', got: {producer_module!r}"
        )
    return f"{consumer_module}.{producer_module}-{QUEUE_GROUP_SUFFIX}"


def compute_dlq_name_for_queue(queue_name: str) -> str:
    return compute_dlq_name(queue_name)


def validate_queue_name(queue_name: str) -> None:
    if not queue_name or not isinstance(queue_name, str):
        raise TopologyValidationError("queue_name must be a non-empty string")
    if not QUEUE_NAME_PATTERN.match(queue_name):
        raise TopologyValidationError(
            f"queue_name must match '<consumer_module>.<producer_module>-events', "
            f"got: {queue_name!r}"
        )


def validate_routing_key(routing_key: str) -> None:
    if not routing_key or not isinstance(routing_key, str):
        raise TopologyValidationError("routing_key must be a non-empty string")
    if not ROUTING_KEY_PATTERN.match(routing_key):
        raise TopologyValidationError(
            f"routing_key must match '<producer_module>.<domain_event>.v<version>', "
            f"got: {routing_key!r}"
        )


def validate_binding(routing_key: str, queue_name: str) -> None:
    validate_routing_key(routing_key)
    validate_queue_name(queue_name)

    routing_segments = routing_key.split(".")
    suffix = f"-{QUEUE_GROUP_SUFFIX}"
    if not queue_name.endswith(suffix):
        raise TopologyValidationError(
            f"queue_name must end with '{suffix}', got: {queue_name!r}"
        )
    queue_base = queue_name[: -len(suffix)]
    queue_segments = queue_base.split(".")

    if len(queue_segments) != 2:
        raise TopologyValidationError(
            f"queue_name must have form 'consumer.producer-events', got: {queue_name!r}"
        )

    queue_producer = queue_segments[1]
    routing_producer = routing_segments[0]

    if routing_producer != queue_producer:
        raise TopologyValidationError(
            f"routing_key producer ({routing_producer}) must match "
            f"queue producer ({queue_producer}) for binding"
        )


def validate_binding_set(
    routing_keys: list[str],
    queue_name: str,
) -> None:
    for rk in routing_keys:
        validate_binding(rk, queue_name)


def validate_exchange_declaration(
    exchange_name: str,
    exchange_type: str,
    durable: bool = True,
) -> None:
    if exchange_name != EXCHANGE_NAME:
        raise TopologyValidationError(
            f"exchange_name must be '{EXCHANGE_NAME}', got: {exchange_name!r}"
        )
    if exchange_type != EXCHANGE_TYPE:
        raise TopologyValidationError(
            f"exchange_type must be '{EXCHANGE_TYPE}', got: {exchange_type!r}"
        )
    if not durable:
        raise TopologyValidationError(
            "exchange must be declared durable"
        )


@dataclass
class TopologyConfig:
    exchange_name: str = EXCHANGE_NAME
    exchange_type: str = EXCHANGE_TYPE
    exchange_durable: bool = True
    consumer_module: str = ""
    producer_module: str = ""
    routing_keys: list[str] = None

    def __post_init__(self):
        if self.routing_keys is None:
            self.routing_keys = []

    @property
    def queue_name(self) -> str:
        return compute_queue_name(self.consumer_module, self.producer_module)

    @property
    def dlq_name(self) -> str:
        return compute_dlq_name(self.queue_name)


def validate_topology_config(config: TopologyConfig) -> None:
    validate_exchange_declaration(
        exchange_name=config.exchange_name,
        exchange_type=config.exchange_type,
        durable=config.exchange_durable,
    )

    if not config.consumer_module:
        raise TopologyValidationError("consumer_module is required")
    if not config.producer_module:
        raise TopologyValidationError("producer_module is required")

    queue_name = config.queue_name

    if not config.routing_keys:
        raise TopologyValidationError(
            f"at least one routing_key is required for queue '{queue_name}'"
        )

    validate_binding_set(config.routing_keys, queue_name)


def extract_producer_from_routing_key(routing_key: str) -> str:
    segments = routing_key.split(".")
    if len(segments) < 1:
        raise TopologyValidationError(
            f"cannot extract producer from routing_key: {routing_key!r}"
        )
    return segments[0]


def extract_version_from_routing_key(routing_key: str) -> int:
    segments = routing_key.split(".")
    if len(segments) < 1:
        raise TopologyValidationError(
            f"cannot extract version from routing_key: {routing_key!r}"
        )
    version_segment = segments[-1]
    if not version_segment.startswith("v"):
        raise TopologyValidationError(
            f"version segment must start with 'v', got: {version_segment!r}"
        )
    try:
        return int(version_segment[1:])
    except ValueError:
        raise TopologyValidationError(
            f"invalid version in routing_key: {routing_key!r}"
        )
