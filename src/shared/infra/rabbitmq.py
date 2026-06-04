
import aio_pika
from aio_pika import ExchangeType, Message, RobustChannel, RobustConnection


class RabbitMQManager:

    def __init__(self, url: str, exchange_name: str) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._connection: RobustConnection | None = None
        self._channel: RobustChannel | None = None
        self._exchange: aio_pika.Exchange | None = None

    @property
    def channel(self) -> RobustChannel:
        if self._channel is not None:
            return self._channel
        raise RuntimeError("RabbitMQManager not connected")

    @property
    def exchange(self) -> aio_pika.Exchange:
        if self._exchange is not None:
            return self._exchange
        raise RuntimeError("RabbitMQManager not connected")

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            name=self._exchange_name,
            type=ExchangeType.TOPIC,
            durable=True,
        )

    async def publish(self, routing_key: str, payload: str, correlation_id: str | None = None) -> None:
        message = Message(
            body=payload.encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=correlation_id or "",
            content_type="application/json",
        )
        await self.exchange.publish(message=message, routing_key=routing_key)

    async def consume(
        self,
        queue_name: str,
        routing_keys: list[str],
        callback,
    ) -> None:
        queue = await self._channel.declare_queue(
            name=queue_name,
            durable=True,
        )
        for key in routing_keys:
            await queue.bind(exchange=self._exchange_name, routing_key=key)
        await queue.consume(callback=callback)

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            self._channel = None
            self._exchange = None

    async def __aenter__(self) -> "RabbitMQManager":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
