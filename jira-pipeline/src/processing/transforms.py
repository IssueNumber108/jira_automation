"""
Data cleaning and transformation.

Operates on Pandas DataFrames after ingestion. Each function is a pure
transform: DataFrame in → DataFrame out, making them easy to compose,
test, and extend.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone

import pandas as pd

from config import settings

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Public pipeline function
# -----------------------------------------------------------------------


def preprocess(
    df: pd.DataFrame,
    issue_types: list[str] | None = None,
) -> pd.DataFrame:
    """
    Run the full cleaning pipeline on a raw DataFrame.

    Steps executed in order:
        1. Strip HTML noise from text fields
        2. Normalise date columns to datetime
        3. Filter to configured issue types
        4. Compute derived columns (age, lag)
        5. Drop fully-empty rows
    """
    df = strip_html_fields(df)
    df = normalise_dates(df)
    df = filter_issue_types(df, issue_types)
    df = add_derived_columns(df)
    df = df.dropna(how="all").reset_index(drop=True)
    logger.info("Preprocessing complete – %d rows remain", len(df))
    return df


# -----------------------------------------------------------------------
# Individual transforms
# -----------------------------------------------------------------------


def strip_html_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Remove HTML tags and decode entities in string columns."""
    tag_re = re.compile(r"<[^>]+>")
    str_cols = df.select_dtypes(include=["object", "string"]).columns

    def _clean(v):
        if pd.isna(v) or not isinstance(v, str) or v.strip() == "":
            return ""
        s = str(v)
        if s == "nan":
            return ""
        return html.unescape(tag_re.sub("", s))

    for col in str_cols:
        df[col] = df[col].apply(_clean)
    return df


def normalise_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert known date columns to pandas datetime (timezone-naive)."""
    date_cols = ["Created", "Updated", "Due Date"]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
            df[col] = df[col].dt.tz_localize(None)  # strip tz for easy math
    return df


def filter_issue_types(
    df: pd.DataFrame,
    issue_types: list[str] | None = None,
) -> pd.DataFrame:
    """Keep only rows whose Issue Type is in the allowed list."""
    if not issue_types or "Issue Type" not in df.columns:
        return df
    before = len(df)
    df = df[df["Issue Type"].isin(issue_types)].reset_index(drop=True)
    logger.info(
        "Issue type filter: %d → %d rows  (types=%s)",
        before,
        len(df),
        issue_types,
    )
    return df


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add computed columns used by analytics / charts.

    - Age_Days        : (today - Created).days  — for open-issue aging
    - Lag_Days        : (today - Due Date).days  — positive = overdue
    - Due_Deviation   : bucketed Lag_Days in N-day intervals
    - Has_Due_Date    : boolean flag
    """
    today = pd.Timestamp(datetime.now(timezone.utc).date())

    if "Created" in df.columns:
        df["Age_Days"] = (today - df["Created"]).dt.days

    if "Due Date" in df.columns:
        df["Has_Due_Date"] = df["Due Date"].notna()
        df["Lag_Days"] = (today - df["Due Date"]).dt.days  # positive = overdue

        bucket = settings.TIME_DEVIATION_BUCKET_DAYS
        df["Due_Deviation_Bucket"] = ((df["Lag_Days"] // bucket) * bucket).astype(
            "Int64"
        )

    return df
