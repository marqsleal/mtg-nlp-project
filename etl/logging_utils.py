from __future__ import annotations

import logging
from datetime import datetime


class PipelineLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().isoformat(timespec="seconds")
        logger_name = record.name
        level = record.levelname
        message = record.getMessage()
        return f"{timestamp} | {logger_name:<50} | {level:<10} | {message}"


def configure_logging(level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        return

    handler = logging.StreamHandler()
    handler.setFormatter(PipelineLogFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
