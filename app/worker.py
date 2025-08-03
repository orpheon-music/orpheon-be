import asyncio

from app.infra.external_services.rabbit_mq_service import AsyncAudioConsumer


async def main():
    # Create and start consumer
    consumer = AsyncAudioConsumer()

    try:
        await consumer.start_consuming()
    finally:
        await consumer.stop_consuming()


if __name__ == "__main__":
    asyncio.run(main())
