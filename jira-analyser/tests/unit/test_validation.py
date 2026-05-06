"""Tests for field validation."""

from __future__ import annotations

import pytest

from jira_analyser.utils.models import JiraIssue
from jira_analyser.validation.validator import FieldValidator, ValidationSpec


def _issue(key: str, **fields: object) -> JiraIssue:
    return JiraIssue(key=key, id=key, fields=dict(fields))


class TestPresenceCheck:
    def test_passes_when_field_present(self) -> None:
        issues = [_issue("A-1", status={"name": "Done"})]
        spec = ValidationSpec(field_id="status")
        report = FieldValidator().validate(issues, specs=[spec])
        assert report.all_clean

    def test_fails_when_field_missing(self) -> None:
        issues = [_issue("A-1")]  # no 'status' key
        spec = ValidationSpec(field_id="status")
        report = FieldValidator().validate(issues, specs=[spec])
        assert not report.all_clean
        assert report.violations_for("status")[0].reason == "missing"

    def test_fails_when_field_is_none(self) -> None:
        issues = [_issue("A-1", status=None)]
        spec = ValidationSpec(field_id="status")
        report = FieldValidator().validate(issues, specs=[spec])
        assert report.violations_for("status")[0].reason == "empty"


class TestAllowedValues:
    def test_passes_when_value_allowed(self) -> None:
        issues = [_issue("A-1", status={"name": "In Progress"})]
        spec = ValidationSpec(field_id="status", allowed_values=["In Progress", "Done"])
        report = FieldValidator().validate(issues, specs=[spec])
        assert report.all_clean

    def test_fails_when_value_not_allowed(self) -> None:
        issues = [_issue("A-1", status={"name": "Unknown"})]
        spec = ValidationSpec(field_id="status", allowed_values=["In Progress", "Done"])
        report = FieldValidator().validate(issues, specs=[spec])
        assert not report.all_clean
        assert report.violations_for("status")[0].reason == "invalid_value"

    def test_case_insensitive_by_default(self) -> None:
        issues = [_issue("A-1", status={"name": "in progress"})]
        spec = ValidationSpec(field_id="status", allowed_values=["In Progress"])
        report = FieldValidator().validate(issues, specs=[spec])
        assert report.all_clean

    def test_case_sensitive_mode(self) -> None:
        issues = [_issue("A-1", status={"name": "in progress"})]
        spec = ValidationSpec(
            field_id="status",
            allowed_values=["In Progress"],
            case_sensitive=True,
        )
        report = FieldValidator().validate(issues, specs=[spec])
        assert not report.all_clean


class TestMultipleSpecs:
    def test_multiple_specs_all_pass(self) -> None:
        issues = [_issue("A-1", status={"name": "Done"}, priority={"name": "High"})]
        specs = [
            ValidationSpec(field_id="status", allowed_values=["Done"]),
            ValidationSpec(field_id="priority", allowed_values=["High", "Medium"]),
        ]
        report = FieldValidator().validate(issues, specs=specs)
        assert report.all_clean

    def test_partial_failure_isolated_to_correct_field(self) -> None:
        issues = [_issue("A-1", status={"name": "Done"}, priority={"name": "Critical"})]
        specs = [
            ValidationSpec(field_id="status", allowed_values=["Done"]),
            ValidationSpec(field_id="priority", allowed_values=["High", "Medium"]),
        ]
        report = FieldValidator().validate(issues, specs=specs)
        assert not report.all_clean
        # status should be clean
        assert not report.violations_for("status")
        # priority should have violation
        assert report.violations_for("priority")
