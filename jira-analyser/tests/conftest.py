"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from jira_analyser.utils.models import FilterResult, JiraIssue


def _make_issue(key: str, **fields: object) -> JiraIssue:
    return JiraIssue(key=key, id=key, fields=dict(fields))


@pytest.fixture()
def sample_issues() -> list[JiraIssue]:
    return [
        _make_issue("PRJ-1", status={"name": "To Do"}, priority={"name": "High"}, created="2024-01-10"),
        _make_issue("PRJ-2", status={"name": "In Progress"}, priority={"name": "Low"}, created="2024-02-15"),
        _make_issue("PRJ-3", status={"name": "Done"}, priority={"name": "High"}, created="2024-03-01"),
        _make_issue("PRJ-4", status=None, priority={"name": "Medium"}, created="2024-03-20"),
    ]


@pytest.fixture()
def sample_filter_result(sample_issues: list[JiraIssue]) -> FilterResult:
    return FilterResult(
        filter_id="99999",
        filter_name="Test Filter",
        issues=sample_issues,
    )
