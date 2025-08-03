from app.config.settings import get_settings
from app.infra.external_services.s3_service import S3Service

settings = get_settings()

s3_client = S3Service(
    secret_key=settings.AWS_S3_SECRET_ACCESS_KEY,
    access_key=settings.AWS_S3_ACCESS_KEY,
    region=settings.AWS_S3_REGION,
    endpoint_url=settings.AWS_S3_URL,
)


def get_s3_client() -> S3Service:
    """
    Dependency to get an S3 client.
    This function is used to get an S3 client.
    """
    return s3_client
