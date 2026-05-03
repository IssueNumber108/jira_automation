"""
Local file loader.

Reads CSV or Excel files from the data/ directory as a fallback when
the Jira fetch is skipped (--local flag).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


class LoaderError(Exception):
    """Raised when a local file cannot be loaded."""


def load_local_file(path: str | Path) -> pd.DataFrame:
    """
    Load a CSV or Excel file into a DataFrame.

    The file extension determines the reader used.
    """
    path = Path(path)
    if not path.exists():
        raise LoaderError(f"File not found: {path}")

    ext = path.suffix.lower()
    logger.info("Loading local file: %s", path)

    if ext == ".csv":
        return pd.read_csv(path, dtype=str)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str, engine="openpyxl")

    raise LoaderError(f"Unsupported file type: {ext}")
