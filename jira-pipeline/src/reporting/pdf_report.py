"""
PDF report generator.

Cover section: title, generation metadata, summary metrics, all charts (2-up grid).
Issue detail table flows directly after the charts (no forced page break).
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import settings
from src.visualization.charts import CHART_REGISTRY

logger = logging.getLogger(__name__)

PAGE_SIZES = {"A4": A4, "LETTER": LETTER}

# ---------------------------------------------------------------------------
# Enterprise colour scheme (mirrors settings.COLORS but in ReportLab format)
# ---------------------------------------------------------------------------
_NAVY = rl_colors.HexColor("#1F3A5F")
_MID_BLUE = rl_colors.HexColor("#4A6FA5")
_SILVER = rl_colors.HexColor("#B0B8C1")
_LIGHT_BG = rl_colors.HexColor("#F5F7FA")
_ALT_BG = rl_colors.HexColor("#EDF0F4")
_BORDER = rl_colors.HexColor("#C4CAD0")
_WHITE = rl_colors.white
_BLACK = rl_colors.HexColor("#1A1A1A")


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def generate_pdf_report(
    df: pd.DataFrame,
    filter_id: str,
    title: str,
    chart_keys: list[str] | None = None,
    output_dir: Path | None = None,
) -> Path:
    """
    Build a PDF report for a single filter and return the output path.

    Parameters
    ----------
    df          : Processed DataFrame (post-cleaning).
    filter_id   : Used in the filename.
    title       : Human-readable title printed on the cover page.
    chart_keys  : List of keys from CHART_REGISTRY to include.
    output_dir  : Destination folder.
    """
    output_dir = output_dir or settings.REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"report_{filter_id}.pdf"

    page_size = PAGE_SIZES.get(settings.PDF_PAGE_SIZE, A4)
    margin = settings.PDF_MARGIN_MM * mm
    page_w, page_h = page_size

    doc = SimpleDocTemplate(
        str(path),
        pagesize=page_size,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )

    styles = getSampleStyleSheet()
    story: list = []

    # ------------------------------------------------------------------ #
    # PAGE 1 – Cover: Title / metadata / summary / charts                 #
    # ------------------------------------------------------------------ #

    # Title
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=_NAVY,
        spaceAfter=4 * mm,
        leading=28,
    )
    story.append(Paragraph(title, title_style))

    # Metadata line
    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontSize=9,
        textColor=_MID_BLUE,
        spaceAfter=6 * mm,
    )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(
        Paragraph(
            f"Filter ID: <b>{filter_id}</b> &nbsp;|&nbsp; "
            f"Generated: {generated} &nbsp;|&nbsp; "
            f"Total issues: <b>{len(df)}</b>",
            meta_style,
        )
    )

    # Horizontal rule (thin 1-row table spanning full width)
    rule_w = page_w - 2 * margin
    story.append(
        Table(
            [[""]],
            colWidths=[rule_w],
            style=TableStyle(
                [
                    ("LINEABOVE", (0, 0), (-1, 0), 1.2, _NAVY),
                    ("LINEBELOW", (0, 0), (-1, 0), 0, _WHITE),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            ),
        )
    )
    story.append(Spacer(1, 5 * mm))

    # Summary section
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=_NAVY,
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    story.append(Paragraph("Summary", heading_style))
    summary_data = _build_summary(df)
    story.append(_make_summary_table(summary_data, rule_w))
    story.append(Spacer(1, 8 * mm))

    # Charts – 2 per row
    chart_keys = chart_keys or list(CHART_REGISTRY.keys())
    figs: list[plt.Figure] = []
    for key in chart_keys:
        factory = CHART_REGISTRY.get(key)
        if factory is None:
            logger.warning("Unknown chart key '%s' – skipping", key)
            continue
        figs.append(factory(df))

    if figs:
        story.append(Paragraph("Analysis Charts", heading_style))
        story.append(Spacer(1, 3 * mm))
        chart_table = _charts_grid(figs, rule_w)
        story.append(chart_table)
        for fig in figs:
            plt.close(fig)

    # ------------------------------------------------------------------ #
    # Issue detail table (flows on after charts – no forced page break)   #
    # ------------------------------------------------------------------ #
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Issue Details", heading_style))
    story.append(Spacer(1, 3 * mm))

    issue_table = _build_issue_table(df, rule_w, styles)
    story.append(issue_table)

    doc.build(story)
    logger.info("PDF report saved → %s", path)
    return path


# -----------------------------------------------------------------------
# Helpers – summary
# -----------------------------------------------------------------------


def _build_summary(df: pd.DataFrame) -> list[list[str]]:
    total = len(df)
    rows: list[list[str]] = [["Metric", "Value"]]

    rows.append(["Total issues", str(total)])

    if "Issue Type" in df.columns:
        for itype, cnt in df["Issue Type"].value_counts().items():
            rows.append([f"  {itype}", str(cnt)])

    if "Has_Due_Date" in df.columns:
        missing = int((~df["Has_Due_Date"]).sum())
        rows.append(["Missing due dates", f"{
                    missing}  ({_pct(missing, total)})"])

    if "Lag_Days" in df.columns:
        overdue = int((df["Lag_Days"] > 0).sum())
        rows.append(["Overdue issues", f"{overdue}  ({_pct(overdue, total)})"])

    if "Age_Days" in df.columns:
        median_age = df["Age_Days"].median()
        rows.append(
            [
                "Median age (days)",
                f"{median_age:.0f}" if pd.notna(median_age) else "N/A",
            ]
        )

    if "Status" in df.columns:
        for status, cnt in df["Status"].value_counts().head(5).items():
            rows.append([f"  Status: {status}", f"{
                        cnt}  ({_pct(cnt, total)})"])

    return rows


def _pct(part: int, whole: int) -> str:
    if whole == 0:
        return "0%"
    return f"{part / whole * 100:.1f}%"


def _make_summary_table(data: list[list[str]], available_width: float) -> Table:
    col_w = [available_width * 0.55, available_width * 0.45]
    table = Table(data, colWidths=col_w, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                # Header row
                ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                # Body rows
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_BG, _WHITE]),
                # Grid
                ("GRID", (0, 0), (-1, -1), 0.4, _BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


# -----------------------------------------------------------------------
# Helpers – chart grid
# -----------------------------------------------------------------------


def _charts_grid(figs: list[plt.Figure], available_width: float) -> Table:
    """Arrange figures 2 per row inside a borderless Table."""
    gap = 4 * mm
    img_w = (available_width - gap) / 2

    images = [_fig_to_image(fig, img_w) for fig in figs]

    rows = []
    for i in range(0, len(images), 2):
        left = images[i]
        right = images[i + 1] if i + 1 < len(images) else ""
        rows.append([left, right])

    table = Table(rows, colWidths=[img_w, img_w], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), gap),
            ]
        )
    )
    return table


def _fig_to_image(fig: plt.Figure, width: float) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=settings.CHART_DPI, bbox_inches="tight")
    buf.seek(0)
    w_in, h_in = fig.get_size_inches()
    return Image(buf, width=width, height=width * (h_in / w_in))


# -----------------------------------------------------------------------
# Helpers – issue detail table
# -----------------------------------------------------------------------

# Column widths as fractions of available page width
_COL_FRACTIONS: dict[str, float] = {
    "Key": 0.08,
    "Assignee": 0.18,
    "Created": 0.13,
    "Due Date": 0.13,
    "Status": 0.13,
    "Priority": 0.10,
    "Issue Type": 0.13,
    "Reporter": 0.18,
    "Summary": 0.38,  # Summary always gets the most space when present
}
_DEFAULT_FRACTION = 0.15


def _build_issue_table(
    df: pd.DataFrame,
    available_width: float,
    styles,
) -> Table:
    columns: list[str] = getattr(
        settings,
        "PDF_ISSUE_TABLE_COLUMNS",
        ["Assignee", "Created", "Due Date", "Summary"],
    )

    # Keep only columns that actually exist in the DataFrame
    columns = [c for c in columns if c in df.columns]
    if not columns:
        return Paragraph("No issue data available.", styles["Normal"])

    # Compute column widths
    raw_fracs = [_COL_FRACTIONS.get(c, _DEFAULT_FRACTION) for c in columns]
    total = sum(raw_fracs)
    col_widths = [available_width * (f / total) for f in raw_fracs]

    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        textColor=_BLACK,
    )
    link_style = ParagraphStyle(
        "CellLink",
        parent=cell_style,
        textColor=_MID_BLUE,
    )
    header_style = ParagraphStyle(
        "CellHeader",
        parent=cell_style,
        fontName="Helvetica-Bold",
        textColor=_WHITE,
        fontSize=8,
    )

    # Build a Key→URL lookup if a Link column is present
    has_links = "Link" in df.columns

    # Header row
    header_row = [Paragraph(col, header_style) for col in columns]
    table_data = [header_row]

    # Data rows
    for _, row in df.iterrows():
        cells = []
        for col in columns:
            val = row.get(col, "")
            if pd.isna(val):
                val = ""
            text = str(val)

            # Render Key as a clickable hyperlink when a URL is available
            if col == "Key" and has_links:
                url = str(row.get("Link", "")).strip()
                if url:
                    cell = Paragraph(
                        f'<link href="{url}"><u>{text}</u></link>', link_style
                    )
                    cells.append(cell)
                    continue

            # Truncate datetime strings to date portion only
            if col in ("Created", "Updated", "Due Date") and "T" in text:
                text = text.split("T")[0]

            cells.append(Paragraph(text, cell_style))
        table_data.append(cells)

    table = Table(
        table_data,
        colWidths=col_widths,
        hAlign="LEFT",
        repeatRows=1,  # repeat header on every page
    )
    table.setStyle(
        TableStyle(
            [
                # Header
                ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 5),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                # Body
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("TOPPADDING", (0, 1), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_BG, _WHITE]),
                # Grid
                ("GRID", (0, 0), (-1, -1), 0.3, _BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                # Left-align all; Summary stays natural (wraps)
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]
        )
    )
    return table
