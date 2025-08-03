import asyncio
import json
import uuid

from aio_pika import DeliveryMode, ExchangeType, Message, connect_robust
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractQueue,
)

from app.config.settings import get_settings


class RabbitMQService:
    def __init__(self):
        self.connection: AbstractConnection | None = None
        self.channel: AbstractChannel | None = None
        self.exchange: AbstractExchange | None = None
        self.processing_queue: AbstractQueue | None = None
        self.retry_queue: AbstractQueue | None = None

    async def connect(self):
        """Establish connection to RabbitMQ"""
        settings = get_settings()
        self.connection = await connect_robust(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            login=settings.RABBITMQ_USER,
            password=settings.RABBITMQ_PASSWORD,
        )
        self.channel = await self.connection.channel()

        # Set QoS - process one message at a time
        await self.channel.set_qos(prefetch_count=1)

        await self._setup_exchanges_and_queues()

    async def disconnect(self):
        """Close connection to RabbitMQ"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()

    async def _setup_exchanges_and_queues(self):
        """Setup exchanges and queues"""
        if not self.channel:
            raise RuntimeError("Channel is not initialized. Call connect() first.")

        # Declare exchange
        self.exchange = await self.channel.declare_exchange(
            "audio.processing", ExchangeType.TOPIC, durable=True
        )

        # Declare queues
        self.processing_queue = await self.channel.declare_queue(
            "audio.processing.jobs",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "audio.processing",
                "x-dead-letter-routing-key": "audio.processing.retry",
            },
        )

        self.retry_queue = await self.channel.declare_queue(
            "audio.processing.retry",
            durable=True,
            arguments={
                "x-message-ttl": 30000,  # 30 seconds delay
                "x-dead-letter-exchange": "audio.processing",
                "x-dead-letter-routing-key": "audio.processing.new",
            },
        )

        # Bind queues to exchange
        await self.processing_queue.bind(self.exchange, "audio.processing.new")
        await self.retry_queue.bind(self.exchange, "audio.processing.retry")

    async def publish_job(self, job_id: uuid.UUID, priority: str = "normal"):
        if not self.exchange:
            raise RuntimeError("Exchange is not initialized. Call connect() first.")

        """Publish job to processing queue"""
        message_body = {  # type: ignore
            "job_id": str(job_id),
            "action": "process",
            "priority": priority,
            "retry_count": 0,
        }

        message = Message(
            json.dumps(message_body).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            priority=1 if priority == "high" else 0,
        )

        await self.exchange.publish(message, routing_key="audio.processing.new")

    async def publish_retry(self, job_id: uuid.UUID, retry_count: int):
        if not self.exchange:
            raise RuntimeError("Exchange is not initialized. Call connect() first.")

        """Publish job to retry queue"""
        message_body = {  # type: ignore
            "job_id": str(job_id),
            "action": "retry",
            "priority": "normal",
            "retry_count": retry_count,
        }

        message = Message(
            json.dumps(message_body).encode(), delivery_mode=DeliveryMode.PERSISTENT
        )

        await self.exchange.publish(message, routing_key="audio.processing.retry")


class AsyncAudioConsumer:
    def __init__(
        self,
    ):
        self.queue_service = RabbitMQService()
        self.is_consuming = False

    async def start_consuming(self):
        """Start consuming messages"""
        if not self.queue_service:
            raise RuntimeError("Queue service is not initialized.")
        await self.queue_service.connect()

        if (
            not self.queue_service.processing_queue
            or not self.queue_service.retry_queue
        ):
            raise RuntimeError(
                "Processing queue is not initialized. Call connect() first."
            )

        # Start consuming from processing queue
        await self.queue_service.processing_queue.consume(
            self._process_message, no_ack=False
        )

        # Start consuming from retry queue
        await self.queue_service.retry_queue.consume(
            self._process_retry_message, no_ack=False
        )

        self.is_consuming = True

        # Keep consuming
        try:
            while self.is_consuming:
                await asyncio.sleep(1)
        finally:
            await self.stop_consuming()

    async def stop_consuming(self):
        """Stop consuming messages"""
        self.is_consuming = False
        await self.queue_service.disconnect()

    async def _process_message(self, message: AbstractIncomingMessage):
        """Process incoming message from main queue"""
        try:
            # Parse message
            body = json.loads(message.body.decode())
            job_id = uuid.UUID(body["job_id"])
            retry_count = body.get("retry_count", 0)

            print(f"Processing job {job_id} with retry count {retry_count}")

            # Acknowledge message on success
            await message.ack()

        except Exception:
            # Handle retry logic
            retry_count = body.get("retry_count", 0)  # type: ignore
            if retry_count < 3:  # Max 3 retries
                await self.queue_service.publish_retry(job_id, retry_count + 1)  # type: ignore
                await message.ack()  # Ack original message
            else:
                await message.reject(requeue=False)  # Send to DLQ

    async def _process_retry_message(self, message: AbstractIncomingMessage):
        """Process retry message - just re-route to main processing"""
        try:
            body = json.loads(message.body.decode())

            # Re-publish to main queue with updated retry count
            await self.queue_service.publish_job(
                uuid.UUID(body["job_id"]), body.get("priority", "normal")
            )

            await message.ack()

        except Exception:
            await message.reject(requeue=False)
