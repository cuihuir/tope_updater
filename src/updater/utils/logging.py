"""Rotating logger setup for updater service."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(
    name: str = "updater",
    log_file: str = "./logs/updater.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 3,
    level: int = logging.INFO,
) -> logging.Logger:
    """Setup rotating file logger with ISO 8601 timestamps.

    Args:
        name: Logger name
        log_file: Path to log file (created if doesn't exist)
        max_bytes: Max size before rotation (default 10MB per FR-018)
        backup_count: Number of rotated files to keep (default 3 per FR-018)
        level: Logging level (DEBUG/INFO/WARN/ERROR per FR-019)

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    # Rotating file handler
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(level)

    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # ISO 8601 timestamp format per FR-019
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
