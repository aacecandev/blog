"""Structured logging configuration for the FastAPI application.

This module provides JSON-formatted logging for production environments
and human-readable logs for development.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any

from .config import settings


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Outputs logs in JSON format for easy parsing by log aggregators
    like ELK, Datadog, or CloudWatch.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "exc_text",
                "thread",
                "threadName",
                "taskName",
                "message",
            ):
                log_entry[key] = value

        return json.dumps(log_entry)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for development logs."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format with colors for terminal output."""
        color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def configure_logging() -> logging.Logger:
    """Configure application logging based on environment.

    Returns:
        Configured logger instance.
    """
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create app logger
    logger = logging.getLogger("dev-blog")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Configure handler based on environment
    handler = logging.StreamHandler(sys.stdout)

    if settings.environment in ("prod", "staging"):
        # Production: JSON format for log aggregators
        handler.setFormatter(JSONFormatter())
    else:
        # Development: colored, human-readable format
        handler.setFormatter(
            ColoredFormatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
            )
        )

    logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)

    return logger


# Configure logging on module import
app_logger = configure_logging()
