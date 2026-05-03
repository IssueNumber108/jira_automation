"""Tests for src.ingestion.parser – Jira JSON → DataFrame conversion."""

import pandas as pd
from src.ingestion.parser import issues_to_dataframe


class TestIssuesToDataframe:
    def test_returns_dataframe(self, sample_raw_issues):
        df = issues_to_dataframe(
            sample_raw_issues, base_url="https://jira.example.com")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_link_column_present(self, sample_raw_issues):
        df = issues_to_dataframe(
            sample_raw_issues, base_url="https://jira.example.com")
        assert "Link" in df.columns
        assert df["Link"].iloc[0].startswith("https://")

    def test_user_columns_appended(self, sample_raw_issues):
        df = issues_to_dataframe(
            sample_raw_issues, base_url="https://jira.example.com")
        assert "Update_Due_Date" in df.columns
        assert "Meeting_Comments" in df.columns
