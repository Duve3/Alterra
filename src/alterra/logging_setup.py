"""Logging configuration using Python standard library."""

import logging
import logging.handlers
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """Configure application logging with console and optional rotating file handler."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger
    root = logging.getLogger()
    root.setLevel(log_level)

    # Clear existing handlers
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(console)

    # File handler (rotating)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(file_handler)

    # Silence noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)