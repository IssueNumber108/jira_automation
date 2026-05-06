"""Jira issue plotting utilities.

Provides a collection of chart-builder functions.  Each function accepts a
``pandas.DataFrame`` (rows = issues) and writes the chart to ``output_dir``.

Available chart types
---------------------
- :func:`bar_chart`          — value counts for a categorical field
- :func:`stacked_bar_chart`  — field A broken down by field B
- :func:`pie_chart`          — proportional view of a categorical field
- :func:`time_series`        — issues over time (line)
- :func:`heatmap`            — cross-tabulation of two categorical fields
- :func:`scatter`            — two numeric fields
- :func:`histogram`          — distribution of a numeric/date field
- :func:`burndown`           — cumulative open vs closed over time

Usage::

    from jira_analyser.plotting.charts import bar_chart, time_series
    import pandas as pd

    df = issues_to_dataframe(filter_results)
    bar_chart(df, field="status", title="Issues by Status")
    time_series(df, date_field="created", freq="W", title="Created per Week")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

from jira_analyser.config import settings
from jira_analyser.utils.logging import get_logger
from jira_analyser.utils.models import FilterResult, JiraIssue

logger = get_logger(__name__)

# ── Aesthetics ────────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({"figure.dpi": 150, "figure.autolayout": True})

_DEFAULT_FIGSIZE = (10, 6)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def issues_to_dataframe(results: list[FilterResult]) -> pd.DataFrame:
    """Flatten filter results into a single :class:`pandas.DataFrame`.

    Each row represents one issue.  All ``fields`` are expanded as top-level
    columns; nested dict values are stringified.
    """
    rows: list[dict[str, Any]] = []
    for result in results:
        for issue in result.issues:
            row: dict[str, Any] = {
                "key": issue.key,
                "id": issue.id,
                "filter_id": result.filter_id,
                "filter_name": result.filter_name or result.filter_id,
            }
            for fid, val in issue.fields.items():
                row[fid] = _flatten_value(val)
            rows.append(row)
    df = pd.DataFrame(rows)
    logger.info("DataFrame shape: %s", df.shape)
    return df


def _flatten_value(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, dict):
        for key in ("name", "value", "displayName", "key"):
            if key in val:
                return val[key]
        return str(val)
    if isinstance(val, list):
        return ", ".join(_flatten_value(v) for v in val)
    return val


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------
def bar_chart(
    df: pd.DataFrame,
    *,
    field: str,
    title: str = "",
    top_n: int | None = None,
    output_dir: Path | None = None,
    filename: str | None = None,
) -> Path:
    """Horizontal bar chart showing value counts for a categorical field."""
    _assert_column(df, field)
    counts = df[field].value_counts()
    if top_n:
        counts = counts.head(top_n)

    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)
    counts.sort_values().plot.barh(ax=ax, color=sns.color_palette("muted")[0])
    ax.set_title(title or f"Issues by {field}")
    ax.set_xlabel("Count")
    ax.set_ylabel(field)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    return _save(fig, filename or f"bar_{field}", output_dir)


def stacked_bar_chart(
    df: pd.DataFrame,
    *,
    x_field: str,
    stack_field: str,
    title: str = "",
    output_dir: Path | None = None,
    filename: str | None = None,
) -> Path:
    """Stacked bar chart: x_field categories broken down by stack_field."""
    _assert_column(df, x_field)
    _assert_column(df, stack_field)

    pivot = df.groupby([x_field, stack_field]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)
    pivot.plot.bar(ax=ax, stacked=True, colormap="tab20")
    ax.set_title(title or f"{x_field} × {stack_field}")
    ax.set_xlabel(x_field)
    ax.set_ylabel("Count")
    ax.legend(title=stack_field, bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.xticks(rotation=45, ha="right")

    return _save(fig, filename or f"stacked_{x_field}_{stack_field}", output_dir)


def pie_chart(
    df: pd.DataFrame,
    *,
    field: str,
    title: str = "",
    top_n: int = 8,
    output_dir: Path | None = None,
    filename: str | None = None,
) -> Path:
    """Pie chart showing proportions of a categorical field."""
    _assert_column(df, field)
    counts = df[field].value_counts().head(top_n)

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(
        counts,
        labels=counts.index,
        autopct="%1.1f%%",
        startangle=140,
        colors=sns.color_palette("pastel"),
    )
    ax.set_title(title or f"Distribution of {field}")

    return _save(fig, filename or f"pie_{field}", output_dir)


def time_series(
    df: pd.DataFrame,
    *,
    date_field: str,
    freq: str = "W",
    title: str = "",
    output_dir: Path | None = None,
    filename: str | None = None,
) -> Path:
    """Line chart of issue count over time, resampled at ``freq``."""
    _assert_column(df, date_field)

    series = (
        pd.to_datetime(df[date_field], utc=True, errors="coerce")
        .dropna()
        .dt.tz_localize(None)
        .value_counts()
        .sort_index()
        .resample(freq)
        .sum()
    )

    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)
    series.plot(ax=ax, marker="o", linewidth=1.5, color=sns.color_palette("muted")[2])
    ax.set_title(title or f"Issues over time ({date_field}, freq={freq})")
    ax.set_xlabel("Date")
    ax.set_ylabel("Count")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    return _save(fig, filename or f"timeseries_{date_field}", output_dir)


def heatmap(
    df: pd.DataFrame,
    *,
    row_field: str,
    col_field: str,
    title: str = "",
    output_dir: Path | None = None,
    filename: str | None = None,
) -> Path:
    """Heatmap showing cross-tabulation of two categorical fields."""
    _assert_column(df, row_field)
    _assert_column(df, col_field)

    ct = pd.crosstab(df[row_field], df[col_field])
    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)
    sns.heatmap(ct, annot=True, fmt="d", cmap="YlOrRd", ax=ax, linewidths=0.5)
    ax.set_title(title or f"Heatmap: {row_field} vs {col_field}")
    ax.set_xlabel(col_field)
    ax.set_ylabel(row_field)

    return _save(fig, filename or f"heatmap_{row_field}_{col_field}", output_dir)


def scatter(
    df: pd.DataFrame,
    *,
    x_field: str,
    y_field: str,
    hue_field: str | None = None,
    title: str = "",
    output_dir: Path | None = None,
    filename: str | None = None,
) -> Path:
    """Scatter plot for two numeric fields, optionally coloured by a third."""
    _assert_column(df, x_field)
    _assert_column(df, y_field)

    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)
    scatter_kwargs: dict[str, Any] = dict(data=df, x=x_field, y=y_field, ax=ax, alpha=0.7)
    if hue_field:
        _assert_column(df, hue_field)
        scatter_kwargs["hue"] = hue_field
    sns.scatterplot(**scatter_kwargs)
    ax.set_title(title or f"{x_field} vs {y_field}")

    return _save(fig, filename or f"scatter_{x_field}_{y_field}", output_dir)


def histogram(
    df: pd.DataFrame,
    *,
    field: str,
    bins: int = 20,
    title: str = "",
    output_dir: Path | None = None,
    filename: str | None = None,
) -> Path:
    """Histogram for a numeric or date-derived field."""
    _assert_column(df, field)

    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)
    numeric = pd.to_numeric(df[field], errors="coerce").dropna()
    if numeric.empty:
        raise ValueError(f"Field '{field}' contains no numeric data for histogram.")
    ax.hist(numeric, bins=bins, color=sns.color_palette("muted")[1], edgecolor="white")
    ax.set_title(title or f"Distribution of {field}")
    ax.set_xlabel(field)
    ax.set_ylabel("Frequency")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    return _save(fig, filename or f"histogram_{field}", output_dir)


def burndown(
    df: pd.DataFrame,
    *,
    created_field: str = "created",
    resolved_field: str = "resolutiondate",
    title: str = "Burndown Chart",
    output_dir: Path | None = None,
    filename: str | None = None,
) -> Path:
    """Cumulative open vs closed issue burndown over time."""
    _assert_column(df, created_field)

    created = (
        pd.to_datetime(df[created_field], utc=True, errors="coerce")
        .dropna()
        .dt.tz_localize(None)
    )

    date_range = pd.date_range(created.min(), pd.Timestamp.today(), freq="D")
    opened = pd.Series(0, index=date_range)
    closed = pd.Series(0, index=date_range)

    for d in created:
        if d in opened.index:
            opened[d] += 1

    if resolved_field in df.columns:
        resolved = (
            pd.to_datetime(df[resolved_field], utc=True, errors="coerce")
            .dropna()
            .dt.tz_localize(None)
        )
        for d in resolved:
            if d in closed.index:
                closed[d] += 1

    cum_open = opened.cumsum() - closed.cumsum()

    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)
    cum_open.plot(ax=ax, color="steelblue", linewidth=2, label="Open issues")
    ax.fill_between(cum_open.index, cum_open, alpha=0.15, color="steelblue")
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Open issues")
    ax.legend()
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    return _save(fig, filename or "burndown", output_dir)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _assert_column(df: pd.DataFrame, field: str) -> None:
    if field not in df.columns:
        raise KeyError(f"Column '{field}' not found in DataFrame. Available: {list(df.columns)}")


def _save(fig: plt.Figure, name: str, output_dir: Path | None) -> Path:
    out = (output_dir or settings.output_dir) / f"{name}.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart saved → %s", out)
    return out
