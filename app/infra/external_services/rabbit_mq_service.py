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
        self.retry_queue: AbstractQueue | None = None
        self.failed_queue: AbstractQueue | None = None

    async def connect(self):
        """Establish connection to RabbitMQ"""
        settings = get_settings()
        try:
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
            logger.info("Successfully connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def disconnect(self):
        """Close connection to RabbitMQ"""
        try:
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
                logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {e}")

    async def _setup_exchanges_and_queues(self):
        """Setup exchanges and queues with proper error handling"""
        if not self.channel:
            raise RuntimeError("Channel is not initialized. Call connect() first.")

        # Declare main exchange
        self.exchange = await self.channel.declare_exchange(
            "audio.processing", ExchangeType.TOPIC, durable=True
        )

        # Declare dead letter exchange for failed messages
        dlx_exchange = await self.channel.declare_exchange(
            "audio.processing.dlx", ExchangeType.TOPIC, durable=True
        )

        # Declare failed messages queue (final destination for permanently failed messages)
        self.failed_queue = await self.channel.declare_queue(
            "audio.processing.failed",
            durable=True,
        )
        await self.failed_queue.bind(dlx_exchange, "audio.processing.failed")

        # Declare retry queue with TTL and dead letter back to main processing
        self.retry_queue = await self.channel.declare_queue(
            "audio.processing.retry",
            durable=True,
            arguments={
                "x-message-ttl": 30000,  # 30 seconds delay before retry
                "x-dead-letter-exchange": "audio.processing",
                "x-dead-letter-routing-key": "audio.processing.new",
            },
        )
        await self.retry_queue.bind(self.exchange, "audio.processing.retry")

        # Declare main processing queue
        self.processing_queue = await self.channel.declare_queue(
            "audio.processing",
            durable=True,
            arguments={
                # Send to DLX (failed queue) when message is rejected
                "x-dead-letter-exchange": "audio.processing.dlx",
                "x-dead-letter-routing-key": "audio.processing.failed",
            },
        )

        # Bind main queue to exchange
        await self.processing_queue.bind(self.exchange, "audio.processing.new")

        logger.info("RabbitMQ exchanges and queues setup completed")

    async def publish_job(
        self,
        job_id: uuid.UUID,
        priority: str = "normal",
        additional_data: dict[str, str] | None = None,
    ):
        """Publish job to processing queue"""
        if not self.exchange:
            raise RuntimeError("Exchange is not initialized. Call connect() first.")

        message_body = { # type: ignore
            "job_id": str(job_id),
            "action": "process",
            "priority": priority,
            "retry_count": 0,  # Track retry attempts
        }

        if additional_data:
            message_body.update(additional_data) # type: ignore

        message = Message(
            json.dumps(message_body).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            priority=1 if priority == "high" else 0,
        )

        await self.exchange.publish(message, routing_key="audio.processing.new")
        logger.info(f"Published job {job_id} to processing queue")


class AsyncAudioConsumer:
    def __init__(self, max_retries: int = 3):
        self.queue_service = RabbitMQService()
        self.ml_service = get_ml_service()
        self.is_consuming = False
        self.max_retries = max_retries

    async def start_consuming(self):
        """Start consuming messages with proper error handling"""
        try:
            await self.queue_service.connect()

            if not self.queue_service.processing_queue:
                raise RuntimeError("Processing queue is not initialized")

            # Start consuming from processing queue
            await self.queue_service.processing_queue.consume(
                self._process_message, no_ack=False
            )

            self.is_consuming = True
            logger.info("Started consuming messages from audio processing queue")

            # Keep consuming
            while self.is_consuming:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error in consumer: {e}")
            raise
        finally:
            await self.stop_consuming()

    async def stop_consuming(self):
        """Stop consuming messages"""
        self.is_consuming = False
        await self.queue_service.disconnect()
        logger.info("Stopped consuming messages")

    async def _process_message(self, message: AbstractIncomingMessage):
        """Process incoming message with retry logic"""
        try:
            logger.info(f"Received message: {message.body.decode()}")

            # Parse message
            body = json.loads(message.body.decode())
            job_id = uuid.UUID(body["job_id"])
            retry_count = body.get("retry_count", 0)

            # Extract file URLs
            voice_file_url = body.get("voice_file_url")
            instrument_file_url = body.get("instrument_file_url")
            reference_file_url = body.get("reference_file_url")

            # Validate required fields
            if not voice_file_url or not reference_file_url:
                logger.error(f"Missing required file URLs for job {job_id}")
                await message.nack(requeue=False)  # Send to failed queue
                return

            logger.info(
                f"Processing job {job_id} (retry: {retry_count}) - "
                f"Voice: {voice_file_url}, Instrument: {instrument_file_url}, "
                f"Reference: {reference_file_url}"
            )

            # Process the job
            is_processing_success = await self.ml_service.process(
                audio_processing_id=str(job_id),
                voice_file_url=voice_file_url,
                reference_file_url=reference_file_url,
            )

            if not is_processing_success:
                raise Exception("ML service processing failed")

            # Acknowledge message on success
            await message.ack()
            logger.info(f"Successfully processed job {job_id}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message: {e}")
            await message.nack(requeue=False)  # Malformed messages go to failed queue

        except ValueError as e:
            logger.error(f"Invalid job_id format: {e}")
            await message.nack(requeue=False)  # Invalid format goes to failed queue

        except Exception as e:
            logger.error(f"Failed to process message: {e}")

            try:
                body = json.loads(message.body.decode())
                retry_count = body.get("retry_count", 0)

                if retry_count < self.max_retries:
                    # Increment retry count and send to retry queue
                    await self._retry_message(message, retry_count + 1)
                else:
                    # Max retries reached, send to failed queue
                    logger.error(
                        f"Max retries ({self.max_retries}) reached for message"
                    )
                    await message.nack(requeue=False)

            except Exception as retry_error:
                logger.error(f"Error handling message retry: {retry_error}")
                await message.nack(requeue=False)

    async def _retry_message(self, message: AbstractIncomingMessage, retry_count: int):
        """Send message to retry queue with updated retry count"""
        try:
            body = json.loads(message.body.decode())
            body["retry_count"] = retry_count

            # Publish to retry queue
            retry_message = Message(
                json.dumps(body).encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
            )

            if self.queue_service.exchange:
                await self.queue_service.exchange.publish(
                    retry_message, routing_key="audio.processing.retry"
                )
                logger.info(f"Sent message to retry queue (attempt {retry_count})")

            # Acknowledge original message
            await message.ack()

        except Exception as e:
            logger.error(f"Failed to retry message: {e}")
            await message.nack(requeue=False)
