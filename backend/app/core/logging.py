import json
import logging
import sys
import time
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Format logs as JSON objects for structured log aggregation systems.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno,
        }

        # Include custom extra attributes
        for key, val in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "module", "msecs",
                "msg", "name", "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName"
            ):
                log_obj[key] = val

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable colored/styled console formatter for local development.
    """
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[41m",  # White on red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        prefix = f"{timestamp} [{color}{record.levelname:^8}{self.RESET}] [{record.name}]"
        message = record.getMessage()

        extra_info = []
        for key, val in record.__dict__.items():
            if key in ("session_id", "trace_id", "patient_phone", "latency_ms", "action"):
                extra_info.append(f"{key}={val}")

        extra_str = f" ({', '.join(extra_info)})" if extra_info else ""
        formatted = f"{prefix}: {message}{extra_str}"

        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        return formatted


def setup_logging(log_level: str = "INFO", log_format: str = "console") -> None:
    """
    Configure root and app loggers with standard structured handlers.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(numeric_level)

    if log_format.lower() == "json":
        stream_handler.setFormatter(JSONFormatter())
    else:
        stream_handler.setFormatter(ConsoleFormatter())

    root_logger.addHandler(stream_handler)

    # Reduce verbosity of third party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Helper to get namespaced loggers.
    """
    return logging.getLogger(name)
