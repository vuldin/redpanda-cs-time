"""
Logging configuration for the application.
"""

import logging
import sys
from typing import Optional


def setup_logger(level: str = 'INFO', log_file: Optional[str] = None,
                 console: bool = True) -> logging.Logger:
    """
    Configure and return the application logger.

    Args:
        level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        log_file: Optional path to log file
        console: Whether to log to console (default: True)

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger('calendar_sync')
    logger.setLevel(getattr(logging, level.upper()))

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    """
    Get the application logger instance.

    Returns:
        Logger instance (creates default if not configured)
    """
    logger = logging.getLogger('calendar_sync')
    if not logger.handlers:
        # Create default logger if not configured
        return setup_logger()
    return logger
