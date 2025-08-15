from app.config.settings import get_settings
from app.infra.external_services.rabbit_mq_service import RabbitMQService

settings = get_settings()

rabbit_mq_service = RabbitMQService()


def get_rabbit_mq_service() -> RabbitMQService:
    """
    Dependency to get RabbitMQ service.
    This function is used to get RabbitMQ service.
    """
    return rabbit_mq_service


async def connect_rabbit_mq():
    """
    Connect to RabbitMQ.
    This function is used to connect to RabbitMQ.
    """
    await rabbit_mq_service.connect()


async def disconnect_rabbit_mq():
    """
    Disconnect from RabbitMQ.
    This function is used to disconnect from RabbitMQ.
    """
    await rabbit_mq_service.disconnect()
