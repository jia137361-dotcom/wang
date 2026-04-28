"""Unified logging configuration for the Pinterest POD Agent.

Call ``setup_logging()`` early in the application entrypoint to configure
structured JSON-line logging with consistent timestamps across all modules.
"""

import logging
import sys
from typing import Any


LOG_FORMAT: dict[str, Any] = {
    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    "datefmt": "%Y-%m-%dT%H:%M:%S",
}

JSON_LOG_FORMAT = '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'


def setup_logging(*, level: int = logging.INFO, json_format: bool = False) -> None:
    fmt = JSON_LOG_FORMAT if json_format else LOG_FORMAT["format"]
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=LOG_FORMAT["datefmt"]))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.WARNING)
