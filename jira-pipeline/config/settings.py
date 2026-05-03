"""
Pipeline configuration.

Edit this file to control every aspect of the pipeline: which filters to run,
which fields to extract, which charts to include, and where outputs land.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (resolved relative to project root, cross-platform)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Ensure output dirs exist at import time
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Jira connection (all sourced from environment variables)
# ---------------------------------------------------------------------------
# e.g. https://jira.example.com
JIRA_URL = os.environ.get("JIRA_URL", "")
# Personal Access Token / service token
JIRA_TOKEN = os.environ.get("JIRA_TOKEN", "")
# Path to .pem client certificate (optional)
JIRA_CERT = os.environ.get("JIRA_CERT", "")

JIRA_API_PATH = "/rest/api/2"
JIRA_MAX_RESULTS = 1000  # per-request page size
JIRA_VERIFY_SSL = True  # set False only for dev/self-signed certs

# ---------------------------------------------------------------------------
# Default filter IDs (used when --filters is not passed via CLI)
# ---------------------------------------------------------------------------
DEFAULT_FILTERS = {
    # filter_id: { per-filter configuration }
    "11111": {
        "title": "Open Change Requests – Q2",
        "issue_types": ["Change Request"],  # CR only
        "charts": [
            "aging_buckets",
            "aging_by_status",
            "overdue_severity",
            "assignee_workload",
            "missing_due_by_assignee",
        ],
    },
    "22222": {
        "title": "Problem Reports – All Open",
        "issue_types": ["Problem Report"],  # PR only
        "charts": [
            "aging_buckets",
            "aging_by_status",
            "overdue_severity",
            "assignee_workload",
            "missing_due_by_assignee",
        ],
    },
    # Add more filters here...
}

# ---------------------------------------------------------------------------
# Jira field mapping
# Key   = friendly column name used in DataFrames / exports
# Value = JQL dot-path inside the Jira issue JSON (fields.<path>)
# ---------------------------------------------------------------------------
JIRA_FIELDS = {
    "Key": "key",
    "Summary": "fields.summary",
    "Status": "fields.status.name",
    "Issue Type": "fields.issuetype.name",
    "Priority": "fields.priority.name",
    "Created": "fields.created",
    "Updated": "fields.updated",
    "Due Date": "fields.duedate",
    "Assignee": "fields.assignee.displayName",
    "Reporter": "fields.reporter.displayName",
}

# Extra empty columns appended to every export for manual user entry
USER_COLUMNS = ["Update_Due_Date", "Meeting_Comments"]

# ---------------------------------------------------------------------------
# Local file fallback (used with --local flag)
# Map filter_id → path to a local CSV or Excel file
# ---------------------------------------------------------------------------
LOCAL_FILES = {
    "11111": DATA_DIR / "filter_11111.csv",
    "22222": DATA_DIR / "filter_22222.csv",
}

# ---------------------------------------------------------------------------
# Export settings
# ---------------------------------------------------------------------------
EXPORT_FORMAT = "xlsx"  # "csv" or "xlsx"

# ---------------------------------------------------------------------------
# Visualization settings
# ---------------------------------------------------------------------------
TIME_DEVIATION_BUCKET_DAYS = 5  # histogram bucket width
CHART_DPI = 150
CHART_STYLE = "seaborn-v0_8-whitegrid"

# Base palette – monochromatic navy for single-colour charts
COLORS = {
    "primary":   "#1F3A5F",  # dark navy
    "secondary": "#4A6FA5",  # medium blue
    "neutral":   "#B0B8C1",  # silver – grid lines, empty-state text
    # Traffic-light scale (multi-colour charts: green=good, red=bad)
    "good":     "#2E7D32",   # green   – healthy / on track
    "warn":     "#F9A825",   # amber   – approaching deadline / moderate age
    "alert":    "#E65100",   # orange  – concerning
    "critical": "#B71C1C",   # red     – overdue / very old
    # Ordered list for cycling (status, assignee, etc.)
    "palette": [
        "#1F3A5F",  # dark navy
        "#4A6FA5",  # medium blue
        "#7A9CC4",  # light blue
        "#A8BCCF",  # pale blue-gray
        "#374151",  # dark slate
        "#6B7280",  # medium gray
        "#9CA3AF",  # light gray
        "#C4CAD0",  # silver
    ],
}

# ---------------------------------------------------------------------------
# PDF report settings
# ---------------------------------------------------------------------------
PDF_PAGE_SIZE = "A4"   # "A4" or "LETTER"
PDF_MARGIN_MM = 20

# Columns shown in the per-issue detail table (must match DataFrame column names).
# "Key" will be rendered as a hyperlink when a "Link" column is present.
PDF_ISSUE_TABLE_COLUMNS = ["Key", "Assignee", "Created", "Due Date", "Summary"]