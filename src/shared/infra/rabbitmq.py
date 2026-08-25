import logging

import aio_pika
from aio_pika import ExchangeType, Message, RobustChannel, RobustConnection

logger = logging.getLogger(__name__)


class RabbitMQManager:
    def __init__(self, url: str, exchange_name: str) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._connection: RobustConnection | None = None
        self._channel: RobustChannel | None = None
        self._exchange: aio_pika.Exchange | None = None
        self._dlx_exchange: aio_pika.Exchange | None = None
        self._consuming_queues: set[str] = set()
        self._consumer_channels: dict[str, RobustChannel] = {}

    @property
    def is_connected(self) -> bool:
        return (
            self._connection is not None
            and self._channel is not None
            and self._exchange is not None
            and not self._connection.is_closed
            and not self._channel.is_closed
        )

    @property
    def channel(self) -> RobustChannel:
        if self._channel is not None and not self._channel.is_closed:
            return self._channel
        raise RuntimeError("RabbitMQManager not connected")

    @property
    def exchange(self) -> aio_pika.Exchange:
        if self.is_connected and self._exchange is not None:
            return self._exchange
        raise RuntimeError("RabbitMQManager not connected")

    async def connect(self) -> None:
        if self.is_connected:
            return

        try:
            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel(
                publisher_confirms=True,
                on_return_raises=True,
            )
            self._exchange = await self._channel.declare_exchange(
                name=self._exchange_name,
                type=ExchangeType.TOPIC,
                durable=True,
            )
            self._dlx_exchange = await self._channel.declare_exchange(
                name=f"{self._exchange_name}.dlx",
                type=ExchangeType.FANOUT,
                durable=True,
            )
        except Exception:
            await self.close()
            raise

        logger.info(
            "RabbitMQ connected exchange=%s publisher_confirms=true",
            self._exchange_name,
        )

    async def declare_topology(
        self,
        queue_name: str,
        routing_keys: list[str],
        dlx_queue_name: str | None = None,
        channel: RobustChannel | None = None,
    ) -> None:
        active_channel = channel or self.channel
        dlq_name = dlx_queue_name or f"{queue_name}.dlq"
        dlq_queue = await active_channel.declare_queue(
            name=dlq_name,
            durable=True,
        )
        queue = await active_channel.declare_queue(
            name=queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": f"{self._exchange_name}.dlx",
                "x-dead-letter-routing-key": dlq_name,
            },
        )
        if self._dlx_exchange is not None:
            await dlq_queue.bind(exchange=self._dlx_exchange.name)
        for key in routing_keys:
            await queue.bind(exchange=self._exchange_name, routing_key=key)

    async def publish(
        self,
        routing_key: str,
        payload: str,
        correlation_id: str | None = None,
        message_id: str | None = None,
    ) -> None:
        message = Message(
            body=payload.encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=correlation_id or "",
            content_type="application/json",
            message_id=message_id or "",
        )
        confirm = await self.exchange.publish(message=message, routing_key=routing_key)
        if confirm is False:
            raise RuntimeError(
                "RabbitMQ did not confirm publication "
                f"routing_key={routing_key} message_id={message_id or ''}"
            )

    async def consume(
        self,
        queue_name: str,
        routing_keys: list[str],
        callback,
        prefetch_count: int | None = None,
    ) -> None:
        if queue_name in self._consuming_queues:
            return

        connection = self._connection
        if connection is None or connection.is_closed:
            raise RuntimeError("RabbitMQManager not connected")
        consumer_channel = await connection.channel()
        if prefetch_count is not None:
            await consumer_channel.set_qos(prefetch_count=max(1, prefetch_count))
        try:
            await self.declare_topology(
                queue_name=queue_name,
                routing_keys=routing_keys,
                channel=consumer_channel,
            )
            queue = await consumer_channel.get_queue(name=queue_name, ensure=True)
            await queue.consume(callback=callback)
        except Exception:
            await consumer_channel.close()
            raise
        self._consumer_channels[queue_name] = consumer_channel
        self._consuming_queues.add(queue_name)
        logger.info(
            "RabbitMQ consumer registered queue=%s routing_keys=%s",
            queue_name,
            routing_keys,
        )

    async def close(self) -> None:
        self._consuming_queues.clear()
        self._consumer_channels.clear()
        connection = self._connection
        self._connection = None
        self._channel = None
        self._exchange = None
        self._dlx_exchange = None
        if connection is not None and not connection.is_closed:
            await connection.close()

    async def __aenter__(self) -> "RabbitMQManager":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
