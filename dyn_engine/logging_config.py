"""Centralised structured logging setup (Phase-1).

Other modules should simply do:

    from dyn_engine.logging_config import get_logger
    logger = get_logger(__name__)

This uses structlog for JSON logs + standard python logging bridge.  Log level
and log file path are controlled via settings.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog

from settings import get_settings


_LOGGER_CONFIGURED = False


def _configure_logging() -> None:
    global _LOGGER_CONFIGURED
    if _LOGGER_CONFIGURED:
        return

    cfg = get_settings()

    log_level = getattr(logging, cfg.log_level.upper(), logging.INFO)

    # Ensure logs directory exists
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path / "dynasty_engine.json.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    stream_handler = logging.StreamHandler()

    # Standard logging format (for non-JSON fallbacks)
    shared_fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    file_handler.setFormatter(logging.Formatter(shared_fmt))
    stream_handler.setFormatter(logging.Formatter(shared_fmt))

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )

    _LOGGER_CONFIGURED = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger, configuring the system on first call."""
    _configure_logging()
    return structlog.get_logger(name)
