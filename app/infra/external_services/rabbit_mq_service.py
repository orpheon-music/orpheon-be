import asyncio
import json
import logging
import uuid

from aio_pika import DeliveryMode, ExchangeType, Message, connect_robust
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractQueue,
)

from app.config.ml_service import get_ml_service
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class RabbitMQService:
    def __init__(self):
        self.connection: AbstractConnection | None = None
        self.channel: AbstractChannel | None = None
        self.exchange: AbstractExchange | None = None
        self.processing_queue: AbstractQueue | None = None

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

        # Bind queues to exchange
        await self.processing_queue.bind(self.exchange, "audio.processing.new")

    async def publish_job(
        self,
        job_id: uuid.UUID,
        priority: str = "normal",
        additional_data: dict[str, str] | None = None,
    ):
        if not self.exchange:
            raise RuntimeError("Exchange is not initialized. Call connect() first.")

        """Publish job to processing queue"""
        message_body: dict[str, str | int] = {  # type: ignore
            "job_id": str(job_id),
            "action": "process",
            "priority": priority,
        }

        if additional_data:
            message_body.update(additional_data)

        message = Message(
            json.dumps(message_body).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            priority=1 if priority == "high" else 0,
        )

        await self.exchange.publish(message, routing_key="audio.processing.new")


class AsyncAudioConsumer:
    def __init__(
        self,
    ):
        self.queue_service = RabbitMQService()
        self.ml_service = get_ml_service()
        self.is_consuming = False

    async def start_consuming(self):
        """Start consuming messages"""
        if not self.queue_service:
            raise RuntimeError("Queue service is not initialized.")
        await self.queue_service.connect()

        if not self.queue_service.processing_queue:
            raise RuntimeError(
                "Processing queue is not initialized. Call connect() first."
            )

        # Start consuming from processing queue
        await self.queue_service.processing_queue.consume(
            self._process_message, no_ack=False
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
            logger.info(f"Received message: {message.body.decode()}")

            # Parse message
            body = json.loads(message.body.decode())
            job_id = uuid.UUID(body["job_id"])

            voice_file_url = body.get("voice_file_url")
            instrument_file_url = body.get("instrument_file_url")
            reference_file_url = body.get("reference_file_url")

            logger.info(
                f"Processing job {job_id} - "
                f"Voice: {voice_file_url}, Instrument: {instrument_file_url}, "
                f"Reference: {reference_file_url}"
            )

            await self.ml_service.process(
                audio_processing_id=str(job_id),
                voice_file_url=voice_file_url,  # type: ignore
                reference_file_url=reference_file_url,  # type: ignore
            )

            # Acknowledge message on success
            await message.ack()

        except Exception:
            logger.warning(f"Failed to process message: {message.body.decode()}")
            await message.nack(requeue=False)
