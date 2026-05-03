"""
Shared pytest fixtures for the test suite.

Provides sample DataFrames that mimic post-ingestion and post-processing
shapes so individual test modules don't have to rebuild them.
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta, timezone


@pytest.fixture
def sample_raw_issues():
    """Minimal list of dicts mimicking Jira API JSON."""
    base = "https://jira.example.com"
    return [
        {
            "key": "CR-101",
            "fields": {
                "summary": "Upgrade auth module",
                "status": {"name": "Open"},
                "issuetype": {"name": "Change Request"},
                "priority": {"name": "High"},
                "created": "2025-01-10T08:00:00.000+0000",
                "updated": "2025-04-01T12:00:00.000+0000",
                "duedate": "2025-03-15",
                "assignee": {"displayName": "Alice"},
                "reporter": {"displayName": "Bob"},
            },
        },
        {
            "key": "PR-202",
            "fields": {
                "summary": "<b>Login fails</b> on Safari &amp; Edge",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Problem Report"},
                "priority": {"name": "Critical"},
                "created": "2025-02-20T10:00:00.000+0000",
                "updated": "2025-04-15T09:00:00.000+0000",
                "duedate": None,
                "assignee": {"displayName": "Charlie"},
                "reporter": {"displayName": "Dana"},
            },
        },
    ]


@pytest.fixture
def sample_dataframe():
    """DataFrame that has already been through ingestion + preprocessing."""
    today = datetime.now(timezone.utc).replace(tzinfo=None)
    return pd.DataFrame(
        {
            "Key": ["CR-1", "CR-2", "PR-3", "PR-4"],
            "Summary": ["Task A", "Task B", "Bug C", "Bug D"],
            "Status": ["Open", "Closed", "Open", "In Progress"],
            "Issue Type": [
                "Change Request",
                "Change Request",
                "Problem Report",
                "Problem Report",
            ],
            "Priority": ["High", "Low", "Critical", "Medium"],
            "Created": pd.to_datetime(
                [
                    today - timedelta(days=90),
                    today - timedelta(days=30),
                    today - timedelta(days=180),
                    today - timedelta(days=10),
                ]
            ),
            "Updated": pd.to_datetime([today] * 4),
            "Due Date": pd.to_datetime(
                [
                    today - timedelta(days=10),
                    today + timedelta(days=5),
                    pd.NaT,
                    today - timedelta(days=45),
                ]
            ),
            "Assignee": ["Alice", "Bob", "Charlie", "Dana"],
            "Reporter": ["Eve", "Eve", "Frank", "Frank"],
            "Link": [
                "https://jira.example.com/browse/CR-1",
                "https://jira.example.com/browse/CR-2",
                "https://jira.example.com/browse/PR-3",
                "https://jira.example.com/browse/PR-4",
            ],
            "Update_Due_Date": ["", "", "", ""],
            "Meeting_Comments": ["", "", "", ""],
            "Age_Days": [90, 30, 180, 10],
            "Has_Due_Date": [True, True, False, True],
            "Lag_Days": [10, -5, pd.NA, 45],
            "Due_Deviation_Bucket": [10, -5, pd.NA, 45],
        }
    )
