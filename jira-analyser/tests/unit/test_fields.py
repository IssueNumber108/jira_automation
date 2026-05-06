"""Tests for field loading helpers (pure logic, no network)."""

from __future__ import annotations

from jira_analyser.fields.loader import (
    _apply_exclusion,
    _apply_selection,
    _apply_type_filter,
    _parse_field,
)
from jira_analyser.utils.models import JiraField


def _make_field(fid: str, name: str, custom: bool = False) -> JiraField:
    return JiraField(id=fid, name=name, custom=custom)


class TestTypeFilter:
    def test_all_returns_everything(self) -> None:
        fields = [_make_field("f1", "F1"), _make_field("cf1", "CF1", custom=True)]
        assert _apply_type_filter(fields, "all") == fields

    def test_standard_excludes_custom(self) -> None:
        fields = [_make_field("f1", "F1"), _make_field("cf1", "CF1", custom=True)]
        result = _apply_type_filter(fields, "standard")
        assert all(not f.custom for f in result)

    def test_custom_excludes_standard(self) -> None:
        fields = [_make_field("f1", "F1"), _make_field("cf1", "CF1", custom=True)]
        result = _apply_type_filter(fields, "custom")
        assert all(f.custom for f in result)


class TestSelection:
    def test_select_by_id(self) -> None:
        fields = [_make_field("status", "Status"), _make_field("priority", "Priority")]
        result = _apply_selection(fields, ["status"])
        assert len(result) == 1 and result[0].id == "status"

    def test_select_by_name_case_insensitive(self) -> None:
        fields = [_make_field("status", "Status"), _make_field("priority", "Priority")]
        result = _apply_selection(fields, ["PRIORITY"])
        assert len(result) == 1 and result[0].id == "priority"


class TestExclusion:
    def test_exclude_by_id(self) -> None:
        fields = [_make_field("comment", "Comment"), _make_field("status", "Status")]
        result = _apply_exclusion(fields, ["comment"])
        assert all(f.id != "comment" for f in result)

    def test_exclude_unknown_id_is_noop(self) -> None:
        fields = [_make_field("status", "Status")]
        result = _apply_exclusion(fields, ["nonexistent"])
        assert len(result) == 1


class TestParseField:
    def test_parses_standard_field(self) -> None:
        raw = {
            "id": "status",
            "name": "Status",
            "custom": False,
            "schema": {"type": "status"},
            "navigable": True,
        }
        f = _parse_field(raw)
        assert f.id == "status"
        assert not f.custom
        assert f.schema_type == "status"
        assert f.navigable is True

    def test_parses_custom_field(self) -> None:
        raw = {
            "id": "customfield_10016",
            "name": "Story Points",
            "custom": True,
            "schema": {"type": "number"},
        }
        f = _parse_field(raw)
        assert f.custom is True
        assert f.name == "Story Points"
