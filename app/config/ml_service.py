from app.config.settings import get_settings
from app.infra.external_services.ml_service import MLService

settings = get_settings()

ml_service = MLService()

def get_ml_service() -> MLService:
    """
    Dependency to get ML service.
    This function is used to get ML service.
    """
    return ml_service

async def connect_ml_service():
    """
    Connect to ML service.
    This function is used to connect to ML service.
    """
    await ml_service.connect()

async def disconnect_ml_service():
    """
    Disconnect from ML service.
    This function is used to disconnect from ML service.
    """
    await ml_service.disconnect()
