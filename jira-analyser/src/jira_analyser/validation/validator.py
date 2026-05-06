"""Field validation across a set of Jira issues.

For each issue, verifies:
1. The field is **present** (key exists and value is not ``None``/empty).
2. The field value is **in the allowed list** (if ``allowed_values`` provided).

Produces a structured :class:`ValidationReport` with per-issue details.

Usage::

    from jira_analyser.validation.validator import FieldValidator, ValidationSpec

    spec = ValidationSpec(
        field_id="status",
        allowed_values=["In Progress", "Done", "To Do"],
    )

    validator = FieldValidator()
    report = validator.validate(issues, specs=[spec])
    report.print_summary()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.table import Table

from jira_analyser.utils.logging import get_logger
from jira_analyser.utils.models import IssueKey, JiraIssue

logger = get_logger(__name__)
_console = Console()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ValidationSpec:
    """Describes what to validate for a single field."""

    field_id: str
    allowed_values: list[str] | None = None  # None = presence-only check
    case_sensitive: bool = False


@dataclass
class IssueFieldViolation:
    """A single validation failure for one issue + field."""

    issue_key: IssueKey
    field_id: str
    reason: str  # "missing" | "empty" | "invalid_value"
    actual_value: Any = None


@dataclass
class FieldValidationResult:
    """Aggregated result for one :class:`ValidationSpec`."""

    spec: ValidationSpec
    violations: list[IssueFieldViolation] = field(default_factory=list)
    checked: int = 0

    @property
    def passed(self) -> int:
        return self.checked - len(self.violations)

    @property
    def is_clean(self) -> bool:
        return not self.violations


@dataclass
class ValidationReport:
    """Container for all validation results across all specs."""

    results: list[FieldValidationResult] = field(default_factory=list)

    @property
    def all_clean(self) -> bool:
        return all(r.is_clean for r in self.results)

    def violations_for(self, field_id: str) -> list[IssueFieldViolation]:
        for r in self.results:
            if r.spec.field_id == field_id:
                return r.violations
        return []

    def print_summary(self) -> None:
        """Print a Rich table summarising the validation run."""
        table = Table(title="Validation Report", show_lines=True)
        table.add_column("Field ID", style="cyan")
        table.add_column("Checked", justify="right")
        table.add_column("Passed", justify="right", style="green")
        table.add_column("Violations", justify="right", style="red")
        table.add_column("Allowed values")

        for r in self.results:
            av = ", ".join(r.spec.allowed_values) if r.spec.allowed_values else "—"
            table.add_row(
                r.spec.field_id,
                str(r.checked),
                str(r.passed),
                str(len(r.violations)),
                av,
            )

        _console.print(table)

        if not self.all_clean:
            _console.print("\n[bold red]Issues with violations:[/bold red]")
            for r in self.results:
                for v in r.violations:
                    _console.print(
                        f"  [yellow]{v.issue_key}[/yellow] / "
                        f"[cyan]{v.field_id}[/cyan]: {v.reason} "
                        f"(actual: [italic]{v.actual_value!r}[/italic])"
                    )


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------
class FieldValidator:
    """Validates a list of issues against one or more :class:`ValidationSpec`."""

    def validate(
        self,
        issues: list[JiraIssue],
        *,
        specs: list[ValidationSpec],
    ) -> ValidationReport:
        """Run all specs over all issues.

        Args:
            issues: Issues to validate.
            specs:  One or more validation specifications.

        Returns:
            A populated :class:`ValidationReport`.
        """
        report = ValidationReport()
        for spec in specs:
            result = self._validate_spec(issues, spec)
            logger.info(
                "Field [cyan]%s[/cyan]: %d checked, %d violations",
                spec.field_id,
                result.checked,
                len(result.violations),
            )
            report.results.append(result)
        return report

    # ── Internal ───────────────────────────────────────────────────────────────
    def _validate_spec(
        self, issues: list[JiraIssue], spec: ValidationSpec
    ) -> FieldValidationResult:
        result = FieldValidationResult(spec=spec, checked=len(issues))

        for issue in issues:
            violation = self._check_issue(issue, spec)
            if violation:
                result.violations.append(violation)

        return result

    @staticmethod
    def _check_issue(
        issue: JiraIssue, spec: ValidationSpec
    ) -> IssueFieldViolation | None:
        raw_value = issue.fields.get(spec.field_id, _SENTINEL)

        # ── Presence check ─────────────────────────────────────────────────────
        if raw_value is _SENTINEL:
            return IssueFieldViolation(
                issue_key=issue.key,
                field_id=spec.field_id,
                reason="missing",
            )

        if raw_value is None or raw_value == "" or raw_value == []:
            return IssueFieldViolation(
                issue_key=issue.key,
                field_id=spec.field_id,
                reason="empty",
                actual_value=raw_value,
            )

        # ── Allowed-values check ───────────────────────────────────────────────
        if spec.allowed_values is None:
            return None  # presence-only spec — passes

        display_value = _extract_display_value(raw_value)
        if not _value_allowed(display_value, spec.allowed_values, spec.case_sensitive):
            return IssueFieldViolation(
                issue_key=issue.key,
                field_id=spec.field_id,
                reason="invalid_value",
                actual_value=display_value,
            )

        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_SENTINEL = object()


def _extract_display_value(raw: Any) -> str:
    """Best-effort extraction of a human-readable string from a Jira field value."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        for key in ("name", "value", "displayName", "key"):
            if key in raw:
                return str(raw[key])
        return str(raw)
    if isinstance(raw, list):
        return ", ".join(_extract_display_value(item) for item in raw)
    return str(raw)


def _value_allowed(value: str, allowed: list[str], case_sensitive: bool) -> bool:
    if case_sensitive:
        return value in allowed
    lower_allowed = {v.lower() for v in allowed}
    return value.lower() in lower_allowed
