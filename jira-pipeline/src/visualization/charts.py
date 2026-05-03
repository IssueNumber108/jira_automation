"""
Chart generators.

Each public function accepts a DataFrame and returns a ``matplotlib.figure.Figure``.
Register new chart types by adding them to ``CHART_REGISTRY`` at the bottom.

Traffic-light colour convention used throughout:
    green  (#2E7D32) = good / on track
    amber  (#F9A825) = warning / moderate
    orange (#E65100) = concerning
    red    (#B71C1C) = critical / overdue
"""

from __future__ import annotations

import logging
from typing import Callable

import matplotlib
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")  # headless – no GUI dependency

from config import settings

logger = logging.getLogger(__name__)

FigureFactory = Callable[[pd.DataFrame], plt.Figure]

# ---------------------------------------------------------------------------
# Shared colour constants
# ---------------------------------------------------------------------------
_GREEN    = settings.COLORS["good"]
_AMBER    = settings.COLORS["warn"]
_ORANGE   = settings.COLORS["alert"]
_RED      = settings.COLORS["critical"]
_NAVY     = settings.COLORS["primary"]
_MID_BLUE = settings.COLORS["secondary"]
_NEUTRAL  = settings.COLORS["neutral"]

# Age / overdue bucket definitions (shared across charts)
_AGE_BINS   = [0,  30,  90, 180, float("inf")]
_AGE_LABELS = ["0–30 d", "31–90 d", "91–180 d", "180+ d"]
_AGE_COLORS = [_GREEN, _AMBER, _ORANGE, _RED]

_OD_BINS   = [0,   7,  30,  90, float("inf")]
_OD_LABELS = ["1–7 d", "8–30 d", "31–90 d", "90+ d"]
_OD_COLORS = [_AMBER, _ORANGE, _RED, "#7B0000"]


# -----------------------------------------------------------------------
# 1. Aging histogram (bucketed bar)
# -----------------------------------------------------------------------

def aging_buckets_chart(df: pd.DataFrame) -> plt.Figure:
    """
    Bucketed bar chart of open-issue age.
    Colour scale: green (fresh) → red (very old).
    """
    if "Age_Days" not in df.columns or df["Age_Days"].dropna().empty:
        return _empty_figure("Issue Aging", "No age data available.")

    data    = df["Age_Days"].dropna()
    buckets = pd.cut(data, bins=_AGE_BINS, labels=_AGE_LABELS, right=True)
    counts  = buckets.value_counts().reindex(_AGE_LABELS, fill_value=0)

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(counts.index, counts.values, color=_AGE_COLORS,
                  edgecolor="white", linewidth=0.8, zorder=3)
    for bar, val in zip(bars, counts.values):
        if val:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.4, str(val),
                    ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_xlabel("Issue age")
    ax.set_ylabel("Number of issues")
    ax.set_title("Issue Aging Distribution", fontweight="bold")
    ax.grid(axis="y", alpha=0.3, zorder=0)
    _legend_patches(ax, zip(_AGE_LABELS, _AGE_COLORS))
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# 2. Aging vs Status (stacked bar)
# -----------------------------------------------------------------------

def aging_by_status_chart(df: pd.DataFrame) -> plt.Figure:
    """
    Stacked bar: age buckets × status.
    Reveals which stages hold the oldest work.
    """
    if "Age_Days" not in df.columns or "Status" not in df.columns:
        return _empty_figure("Aging by Status", "Requires Age_Days and Status columns.")

    df2 = df.copy()
    df2["Age_Bucket"] = pd.cut(df2["Age_Days"], bins=_AGE_BINS,
                                labels=_AGE_LABELS, right=True)
    pivot = (
        df2.groupby(["Age_Bucket", "Status"], observed=True)
        .size()
        .unstack(fill_value=0)
        .reindex(_AGE_LABELS)
    )
    if pivot.empty:
        return _empty_figure("Aging by Status", "No data to display.")

    statuses = pivot.columns.tolist()
    palette  = settings.COLORS["palette"]
    colors   = [palette[i % len(palette)] for i in range(len(statuses))]

    fig, ax = plt.subplots(figsize=(9, 4))
    bottom = np.zeros(len(pivot))
    for status, color in zip(statuses, colors):
        vals = pivot[status].values
        ax.bar(pivot.index, vals, bottom=bottom, label=status,
               color=color, edgecolor="white", linewidth=0.5, zorder=3)
        bottom += vals

    ax.set_xlabel("Issue age bucket")
    ax.set_ylabel("Number of issues")
    ax.set_title("Aging by Status (stacked)", fontweight="bold")
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.legend(title="Status", bbox_to_anchor=(1.01, 1), loc="upper left",
              fontsize=8, title_fontsize=8)
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# 3. Overdue severity
# -----------------------------------------------------------------------

def overdue_severity_chart(df: pd.DataFrame) -> plt.Figure:
    """
    How overdue are overdue issues? Bucketed bar with traffic-light colours.
    """
    if "Lag_Days" not in df.columns:
        return _empty_figure("Overdue Severity", "No lag data available.")

    overdue = df.loc[df["Lag_Days"] > 0, "Lag_Days"].dropna()
    if overdue.empty:
        return _empty_figure("Overdue Severity", "No overdue issues – great job!")

    buckets = pd.cut(overdue, bins=_OD_BINS, labels=_OD_LABELS, right=True)
    counts  = buckets.value_counts().reindex(_OD_LABELS, fill_value=0)

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(counts.index, counts.values, color=_OD_COLORS,
                  edgecolor="white", linewidth=0.8, zorder=3)
    for bar, val in zip(bars, counts.values):
        if val:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.4, str(val),
                    ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_xlabel("Days overdue")
    ax.set_ylabel("Number of issues")
    ax.set_title("Overdue Severity", fontweight="bold")
    ax.grid(axis="y", alpha=0.3, zorder=0)
    _legend_patches(ax, zip(_OD_LABELS, _OD_COLORS))
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# 4. Assignee workload vs overdue (stacked bar)
# -----------------------------------------------------------------------

def assignee_workload_chart(df: pd.DataFrame) -> plt.Figure:
    """
    Stacked bar per assignee: green = on-track, red = overdue.
    Exposes imbalance and accountability gaps.
    """
    if "Assignee" not in df.columns:
        return _empty_figure("Assignee Workload", "No Assignee column found.")

    df2 = df.copy()
    df2["_overdue"] = df2.get("Lag_Days", pd.Series(dtype=float)) > 0

    grp = df2.groupby("Assignee")["_overdue"].agg(
        total="count", overdue="sum"
    ).reset_index()
    grp["on_track"] = grp["total"] - grp["overdue"]
    grp = grp.sort_values("total", ascending=False)
    grp["label"] = grp["Assignee"].apply(_short_name)

    fig, ax = plt.subplots(figsize=(max(7, len(grp) * 0.9), 4))
    x = np.arange(len(grp))
    ax.bar(x, grp["on_track"], color=_GREEN, label="On track",
           edgecolor="white", linewidth=0.6, zorder=3)
    ax.bar(x, grp["overdue"], bottom=grp["on_track"], color=_RED,
           label="Overdue", edgecolor="white", linewidth=0.6, zorder=3)

    for i, (_, row) in enumerate(grp.iterrows()):
        if row["total"]:
            pct = row["overdue"] / row["total"] * 100
            color = _RED if pct > 50 else _AMBER
            ax.text(i, row["total"] + 0.3, f"{pct:.0f}%",
                    ha="center", va="bottom", fontsize=8, color=color,
                    fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(grp["label"], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Number of issues")
    ax.set_title("Assignee Workload vs Overdue", fontweight="bold")
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# 5. Missing due dates by assignee
# -----------------------------------------------------------------------

def missing_due_by_assignee_chart(df: pd.DataFrame) -> plt.Figure:
    """
    Bar chart: count of issues without a due date, per assignee.
    Highlights governance / process gaps.
    """
    if "Assignee" not in df.columns or "Has_Due_Date" not in df.columns:
        return _empty_figure("Missing Due Dates", "Requires Assignee and Has_Due_Date columns.")

    missing = (
        df[~df["Has_Due_Date"]]
        .groupby("Assignee")
        .size()
        .sort_values(ascending=False)
    )
    if missing.empty:
        return _empty_figure("Missing Due Dates by Assignee",
                              "All issues have a due date – excellent!")

    labels = [_short_name(a) for a in missing.index]
    colors = [_RED if v >= 4 else (_ORANGE if v >= 2 else _AMBER)
              for v in missing.values]

    fig, ax = plt.subplots(figsize=(max(6, len(missing) * 0.9), 4))
    bars = ax.bar(labels, missing.values, color=colors,
                  edgecolor="white", linewidth=0.6, zorder=3)
    for bar, val in zip(bars, missing.values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.1, str(val),
                ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_ylabel("Issues missing due date")
    ax.set_title("Missing Due Dates by Assignee", fontweight="bold")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.grid(axis="y", alpha=0.3, zorder=0)
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# Legacy charts (kept for backwards-compatibility / optional use)
# -----------------------------------------------------------------------

def time_deviation_chart(df: pd.DataFrame) -> plt.Figure:
    col = "Due_Deviation_Bucket"
    if col not in df.columns or df[col].dropna().empty:
        return _empty_figure("Time Deviation", "No due-date deviation data available.")

    data   = df[col].dropna().astype(int)
    bucket = settings.TIME_DEVIATION_BUCKET_DAYS
    bins   = np.arange(data.min() - bucket, data.max() + 2 * bucket, bucket)

    fig, ax = plt.subplots(figsize=(9, 4))
    counts, edges, patches = ax.hist(data, bins=bins, edgecolor="white",
                                     linewidth=0.6, color=_MID_BLUE, zorder=3)
    for patch, left_edge in zip(patches, edges[:-1]):
        if left_edge >= 0:
            patch.set_facecolor(_RED)

    ax.set_xlabel("Days past due  (negative = ahead of schedule)")
    ax.set_ylabel("Number of issues")
    ax.set_title("Time Deviation Analysis", fontweight="bold")
    ax.axvline(0, color=_NEUTRAL, linestyle="--", linewidth=1)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def missing_due_dates_chart(df: pd.DataFrame) -> plt.Figure:
    if "Has_Due_Date" not in df.columns:
        return _empty_figure("Missing Due Dates", "No due-date column found.")

    counts = df["Has_Due_Date"].value_counts()
    values = [counts.get(True, 0), counts.get(False, 0)]

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(["Has Due Date", "Missing Due Date"], values,
                  color=[_GREEN, _RED], edgecolor="white", linewidth=0.8, zorder=3)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5, str(val),
                ha="center", va="bottom", fontweight="bold")
    ax.set_ylabel("Number of issues")
    ax.set_title("Due Date Coverage", fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def status_distribution_chart(df: pd.DataFrame) -> plt.Figure:
    if "Status" not in df.columns or df["Status"].dropna().empty:
        return _empty_figure("Status Distribution", "No status data available.")

    counts  = df["Status"].value_counts()
    palette = settings.COLORS["palette"]
    colors  = [palette[i % len(palette)] for i in range(len(counts))]

    fig, ax = plt.subplots(figsize=(7, 5))
    _, _, autotexts = ax.pie(
        counts.values, labels=counts.index, autopct="%1.1f%%",
        colors=colors, startangle=140, pctdistance=0.8,
    )
    for t in autotexts:
        t.set_fontsize(9)
    ax.set_title("Issue Status Distribution", fontweight="bold")
    fig.tight_layout()
    return fig


def aging_analysis_chart(df: pd.DataFrame) -> plt.Figure:
    """Alias for aging_buckets (backwards-compat)."""
    return aging_buckets_chart(df)


def lagging_behind_chart(df: pd.DataFrame) -> plt.Figure:
    """Alias for overdue_severity (backwards-compat)."""
    return overdue_severity_chart(df)


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _short_name(name: str) -> str:
    """'Alice Martin' → 'Alice M.'"""
    parts = str(name).split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[-1][0]}."
    return name


def _legend_patches(ax, label_color_pairs) -> None:
    patches = [mpatches.Patch(color=c, label=lbl)
               for lbl, c in label_color_pairs]
    ax.legend(handles=patches, fontsize=8, loc="upper right")


def _empty_figure(title: str, message: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.text(0.5, 0.5, message, ha="center", va="center",
            fontsize=13, color=_NEUTRAL, transform=ax.transAxes)
    ax.set_title(title, fontweight="bold")
    ax.axis("off")
    fig.tight_layout()
    return fig


# -----------------------------------------------------------------------
# Chart registry
# -----------------------------------------------------------------------

CHART_REGISTRY: dict[str, FigureFactory] = {
    # Primary analytical charts
    "aging_buckets":           aging_buckets_chart,
    "aging_by_status":         aging_by_status_chart,
    "overdue_severity":        overdue_severity_chart,
    "assignee_workload":       assignee_workload_chart,
    "missing_due_by_assignee": missing_due_by_assignee_chart,
    # Legacy / optional
    "time_deviation":          time_deviation_chart,
    "missing_due_dates":       missing_due_dates_chart,
    "status_distribution":     status_distribution_chart,
    "aging":                   aging_analysis_chart,
    "lagging_behind":          lagging_behind_chart,
}