"""
Shared logging configuration for QuickScribe services.
Provides a simple get_logger function that returns standard Python loggers.
Each service can configure its own logging handlers and formatters.
"""

import logging


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    Args:
        name: Name of the logger (usually module name)

    Returns:
        A configured logger instance
    """
    logger = logging.getLogger(f"quickscribe.{name}")

    # Set default level if not already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)

    return logger
