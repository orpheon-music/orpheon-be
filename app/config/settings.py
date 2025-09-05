from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "orpheon_be"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # JWT
    JWT_SECRET_KEY: str = "your_jwt_secret_key"
    JWT_EXPIRES_IN: int = 3600

    # AWS S3
    AWS_S3_ACCESS_KEY: str = "your_aws_access_key"
    AWS_S3_SECRET_ACCESS_KEY: str = "your_aws_secret_access_key"
    AWS_S3_REGION: str = "us-west-2"
    AWS_S3_URL: str = "https://s3.amazonaws.com"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # RabbitMQ
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"

    # ML Service
    ML_SERVICE_HOST: str = "localhost"
    ML_SERVICE_PORT: int = 5000

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    """
    Get the settings instance.
    This function is used to get the settings instance.
    """
    return Settings()
