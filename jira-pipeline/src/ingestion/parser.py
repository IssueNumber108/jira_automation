"""
Jira JSON → Pandas DataFrame parser.

Extracts configured fields from raw Jira API issue payloads and builds
a clean DataFrame with ticket hyperlinks.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from config import settings

logger = logging.getLogger(__name__)


def _resolve_dot_path(obj: dict, dot_path: str) -> Any:
    """
    Traverse a nested dict using a dot-separated path.

    Example: _resolve_dot_path(issue, "fields.status.name")
    """
    parts = dot_path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def issues_to_dataframe(
    issues: list[dict[str, Any]],
    base_url: str | None = None,
) -> pd.DataFrame:
    """
    Convert a list of raw Jira issue dicts into a DataFrame.

    Columns are determined by ``config.settings.JIRA_FIELDS``.
    A ``Link`` column with the full ticket URL is appended.
    """
    base_url = (base_url or settings.JIRA_URL).rstrip("/")
    rows: list[dict[str, Any]] = []

    for issue in issues:
        row: dict[str, Any] = {}
        for col_name, dot_path in settings.JIRA_FIELDS.items():
            row[col_name] = _resolve_dot_path(issue, dot_path)
        # Ticket hyperlink
        key = row.get("Key", "")
        row["Link"] = f"{base_url}/browse/{key}" if key else ""
        rows.append(row)

    df = pd.DataFrame(rows)

    # Append empty user columns
    for col in settings.USER_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    logger.info(
        "Parsed %d issues into DataFrame (%d columns)", len(
            df), len(df.columns)
    )
    return df
