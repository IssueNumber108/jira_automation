"""
Raw data exporter.

Saves a DataFrame to CSV or Excel in the configured data directory.
Each filter ID gets its own file.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from config import settings

logger = logging.getLogger(__name__)


def export_raw(
    df: pd.DataFrame,
    filter_id: str,
    fmt: str | None = None,
    output_dir: Path | None = None,
) -> Path:
    """
    Write *df* to disk and return the output path.

    Parameters
    ----------
    df : DataFrame to export.
    filter_id : Used to name the file (``filter_<id>.<ext>``).
    fmt : ``"csv"`` or ``"xlsx"``.  Falls back to ``settings.EXPORT_FORMAT``.
    output_dir : Destination folder.  Falls back to ``settings.DATA_DIR``.
    """
    fmt = (fmt or settings.EXPORT_FORMAT).lower()
    output_dir = output_dir or settings.DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"filter_{filter_id}.{fmt}"
    path = output_dir / filename

    if fmt == "csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
    elif fmt in ("xlsx", "xls"):
        df.to_excel(path, index=False, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported export format: {fmt}")

    logger.info("Exported %d rows → %s", len(df), path)
    return path
