"""Tests for src.processing.transforms – cleaning and derived columns."""

import pandas as pd
from src.processing.transforms import (
    strip_html_fields,
    normalise_dates,
    filter_issue_types,
    add_derived_columns,
)


class TestStripHtml:
    def test_removes_tags(self):
        df = pd.DataFrame({"Summary": ["<b>Bold</b> text"]})
        result = strip_html_fields(df)
        assert "<b>" not in result["Summary"].iloc[0]

    def test_decodes_entities(self):
        df = pd.DataFrame({"Summary": ["A &amp; B"]})
        result = strip_html_fields(df)
        assert "A & B" in result["Summary"].iloc[0]


class TestFilterIssueTypes:
    def test_filters_correctly(self, sample_dataframe):
        result = filter_issue_types(sample_dataframe, ["Change Request"])
        assert all(result["Issue Type"] == "Change Request")

    def test_no_filter_returns_all(self, sample_dataframe):
        result = filter_issue_types(sample_dataframe, None)
        assert len(result) == len(sample_dataframe)


class TestDerivedColumns:
    def test_age_days_created(self, sample_dataframe):
        # Remove existing derived cols to test fresh computation
        df = sample_dataframe.drop(
            columns=["Age_Days", "Has_Due_Date",
                     "Lag_Days", "Due_Deviation_Bucket"],
            errors="ignore",
        )
        result = add_derived_columns(df)
        assert "Age_Days" in result.columns
        assert "Lag_Days" in result.columns
        assert "Has_Due_Date" in result.columns
