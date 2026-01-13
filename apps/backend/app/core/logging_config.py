"""
Logging configuration for place-research.

Provides structured logging with JSON output for production and
human-readable output for development. Includes request ID tracking,
log context management, and performance metrics.
"""

import logging
import sys
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Optional

from pythonjsonlogger import json as jsonlogger

# Context variable for request ID (thread-safe across async contexts)
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# Context variable for additional log context
log_context_var: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})


class ContextFilter(logging.Filter):
    """Add request ID and custom context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Add request ID if available
        record.request_id = request_id_var.get() or "-"

        # Add any custom context
        context = log_context_var.get()
        for key, value in context.items():
            setattr(record, key, value)

        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(self, log_data: dict, record: logging.LogRecord, message_dict: dict):
        super().add_fields(log_data, record, message_dict)

        # Add timestamp in ISO format
        log_data["timestamp"] = datetime.now(UTC).isoformat()

        # Add log level
        log_data["level"] = record.levelname

        # Add logger name
        log_data["logger"] = record.name

        # Add request ID if present
        request_id = getattr(record, "request_id", None)
        if request_id and request_id != "-":
            log_data["request_id"] = request_id

        # Add any extra context
        context = log_context_var.get()
        if context:
            log_data["context"] = context


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output in development."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record: logging.LogRecord) -> str:
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{self.BOLD}{levelname}{self.RESET}"

        # Format the message
        formatted = super().format(record)

        # Reset levelname for next use
        record.levelname = levelname

        return formatted


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    app_name: str = "place-research",
) -> None:
    """
    Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type - "json" for production, "text" for development
        app_name: Application name to include in logs
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers = []

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    # Add context filter
    context_filter = ContextFilter()
    console_handler.addFilter(context_filter)

    # Set formatter based on format type
    if log_format == "json":
        # JSON formatter for production
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(logger)s %(message)s",
            json_ensure_ascii=False,
        )
    else:
        # Colored text formatter for development
        if log_format == "color":
            formatter = ColoredFormatter(
                "%(asctime)s [%(levelname)s] %(name)s - %(message)s [%(request_id)s]",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        else:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s - %(message)s [%(request_id)s]",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set specific log levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Suppress SQLAlchemy logging noise
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)

    root_logger.info(
        "Logging configured: level=%s, format=%s, app=%s",
        log_level,
        log_format,
        app_name,
    )


def set_request_id(request_id: str) -> None:
    """Set the request ID for the current context."""
    request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    """Get the current request ID."""
    return request_id_var.get()


def set_log_context(**kwargs: Any) -> None:
    """Set additional context for logging."""
    context = log_context_var.get().copy()
    context.update(kwargs)
    log_context_var.set(context)


def clear_log_context() -> None:
    """Clear the log context."""
    log_context_var.set({})


def get_log_context() -> dict[str, Any]:
    """Get the current log context."""
    return log_context_var.get()


class LogTimer:
    """Context manager for timing operations and logging duration."""

    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        level: int = logging.INFO,
        **context: Any,
    ):
        self.logger = logger
        self.operation = operation
        self.level = level
        self.context = context
        self.start_time: Optional[float] = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        self.logger.log(
            self.level,
            f"Starting {self.operation}",
            extra={"operation": self.operation, **self.context},
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is None:
            return

        duration_ms = (time.perf_counter() - self.start_time) * 1000

        if exc_type is not None:
            # Log error with duration
            self.logger.error(
                f"Failed {self.operation} after {duration_ms:.2f}ms: {exc_val}",
                extra={
                    "operation": self.operation,
                    "duration_ms": duration_ms,
                    "error": str(exc_val),
                    "error_type": exc_type.__name__,
                    **self.context,
                },
            )
        else:
            # Log success with duration
            self.logger.log(
                self.level,
                f"Completed {self.operation} in {duration_ms:.2f}ms",
                extra={
                    "operation": self.operation,
                    "duration_ms": duration_ms,
                    **self.context,
                },
            )


def log_function_call(logger: logging.Logger, level: int = logging.DEBUG):
    """Decorator to log function calls with arguments and return values."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.log(
                level,
                f"Calling {func_name}",
                extra={
                    "function": func_name,
                    "args": str(args)[:100],  # Truncate for safety
                    "kwargs": str(kwargs)[:100],
                },
            )

            try:
                result = func(*args, **kwargs)
                logger.log(
                    level,
                    f"Completed {func_name}",
                    extra={"function": func_name, "success": True},
                )
                return result
            except Exception as e:
                logger.error(
                    f"Error in {func_name}: {e}",
                    extra={
                        "function": func_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator
