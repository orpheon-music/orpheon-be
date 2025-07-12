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

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    """
    Get the settings instance.
    This function is used to get the settings instance.
    """
    return Settings()
