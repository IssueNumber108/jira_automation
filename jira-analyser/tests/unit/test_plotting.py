"""Tests for plotting helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from jira_analyser.plotting.charts import issues_to_dataframe
from jira_analyser.utils.models import FilterResult, JiraIssue


def _issue(key: str, **fields: object) -> JiraIssue:
    return JiraIssue(key=key, id=key, fields=dict(fields))


@pytest.fixture()
def sample_result() -> FilterResult:
    return FilterResult(
        filter_id="1",
        filter_name="Test",
        issues=[
            _issue("A-1", status={"name": "Done"}, priority={"name": "High"}),
            _issue("A-2", status={"name": "To Do"}, priority={"name": "Low"}),
            _issue("A-3", status={"name": "Done"}, priority={"name": "High"}),
        ],
    )


def test_dataframe_has_correct_shape(sample_result: FilterResult) -> None:
    df = issues_to_dataframe([sample_result])
    assert len(df) == 3
    assert "key" in df.columns
    assert "status" in df.columns


def test_nested_dict_values_are_flattened(sample_result: FilterResult) -> None:
    df = issues_to_dataframe([sample_result])
    assert set(df["status"].unique()).issubset({"Done", "To Do"})


def test_bar_chart_writes_file(tmp_path: Path, sample_result: FilterResult) -> None:
    from jira_analyser.plotting.charts import bar_chart

    df = issues_to_dataframe([sample_result])
    out = bar_chart(df, field="status", output_dir=tmp_path)
    assert out.exists()
    assert out.suffix == ".png"


def test_pie_chart_writes_file(tmp_path: Path, sample_result: FilterResult) -> None:
    from jira_analyser.plotting.charts import pie_chart

    df = issues_to_dataframe([sample_result])
    out = pie_chart(df, field="priority", output_dir=tmp_path)
    assert out.exists()


def test_missing_column_raises(sample_result: FilterResult) -> None:
    from jira_analyser.plotting.charts import bar_chart

    df = issues_to_dataframe([sample_result])
    with pytest.raises(KeyError, match="nonexistent"):
        bar_chart(df, field="nonexistent", output_dir=Path("/tmp"))
