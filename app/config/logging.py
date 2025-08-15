import logging
import logging.config
import os
import sys


def setup_logging():
    """
    Initializes and configures the application's logger.

    This setup uses a dictionary-based configuration for clarity and ease of
    modification. It directs logs to standard output with a consistent format.

    The log level can be controlled via the `LOG_LEVEL` environment variable.
    If not set, it defaults to 'INFO'.

    It also intercepts logs from Uvicorn to ensure all output from the
    application and the server shares the same formatting and destination.

    Returns:
        logging.Logger: A configured logger instance for the application.
    """

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    LOGGING_CONFIG = {  # type: ignore
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "logging.Formatter",
                "fmt": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
            },
        },
         "root": {
            "level": log_level,
            "handlers": ["default"],
        },
        "loggers": {
            "orpheon_be": {
                "handlers": ["default"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(LOGGING_CONFIG)  # type: ignore

    return logging.getLogger("orpheon_be")
