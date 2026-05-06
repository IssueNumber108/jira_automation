"""Centralised logging configuration using Rich."""

from __future__ import annotations

import logging

from rich.logging import RichHandler

_configured = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured with Rich output (idempotent)."""
    global _configured
    if not _configured:
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True, markup=True)],
        )
        _configured = True
    return logging.getLogger(name)
