"""Analysis pipeline orchestrator.

Defines a :class:`PipelineConfig` that fully describes one analysis run, and a
:func:`run_pipeline` function that executes every step in order:

1. (Optional) Generate TLS certificate
2. Load Jira fields
3. Fetch issues for all configured filters
4. Validate field values
5. Build all configured charts

Each step is independently logged and its output is passed to the next.

Usage (library)::

    from jira_analyser.pipeline.runner import PipelineConfig, run_pipeline
    from jira_analyser.validation.validator import ValidationSpec

    config = PipelineConfig(
        filter_ids=["12345", "67890"],
        field_type="all",
        exclude_fields=["comment", "worklog"],
        validation_specs=[
            ValidationSpec(field_id="status", allowed_values=["To Do", "In Progress", "Done"]),
        ],
        charts=["bar:status", "time_series:created", "burndown"],
    )
    run_pipeline(config)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from jira_analyser.fields import FieldLoader, FieldType
from jira_analyser.filters import fetch_issues_for_filters
from jira_analyser.plotting import charts as ch
from jira_analyser.utils.logging import get_logger
from jira_analyser.utils.models import FilterResult, JiraField
from jira_analyser.validation import FieldValidator, ValidationReport, ValidationSpec

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pipeline configuration
# ---------------------------------------------------------------------------
@dataclass
class PipelineConfig:
    """Describes a complete analysis run.

    Attributes:
        filter_ids:        Jira filter IDs to fetch issues from.
        field_type:        Which fields to load: ``"all"``, ``"standard"``, ``"custom"``.
        select_fields:     Whitelist of field IDs/names (overrides ``exclude_fields``).
        exclude_fields:    Blacklist of field IDs/names to drop.
        fetch_fields:      Fields to request per issue (``None`` = all).
        validation_specs:  Validation rules to apply.
        charts:            Chart specs — see :func:`_parse_chart_spec` for format.
        output_dir:        Override the default output directory.
        generate_cert:     If ``True``, regenerate the TLS certificate before running.
        cert_out_dir:      Where to write the generated certificate.
    """

    filter_ids: list[str]
    field_type: FieldType = "all"
    select_fields: list[str] | None = None
    exclude_fields: list[str] | None = None
    fetch_fields: list[str] | None = None
    validation_specs: list[ValidationSpec] = field(default_factory=list)
    charts: list[str] = field(default_factory=list)
    output_dir: Path | None = None
    generate_cert: bool = False
    cert_out_dir: Path = Path("certs")


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------
def run_pipeline(config: PipelineConfig) -> dict[str, Any]:
    """Execute the full analysis pipeline.

    Args:
        config: Fully populated :class:`PipelineConfig`.

    Returns:
        Dict with keys: ``fields``, ``filter_results``, ``dataframe``,
        ``validation_report``, ``chart_paths``.
    """
    logger.info("[bold blue]═══ Jira Analyser Pipeline Start ═══[/bold blue]")

    # ── Step 0: cert (optional) ───────────────────────────────────────────────
    if config.generate_cert:
        _step_generate_cert(config.cert_out_dir)

    # ── Step 1: fields ────────────────────────────────────────────────────────
    fields = _step_load_fields(config)

    # ── Step 2: fetch issues ──────────────────────────────────────────────────
    filter_results = _step_fetch_issues(config)

    # ── Step 3: build DataFrame ───────────────────────────────────────────────
    df = ch.issues_to_dataframe(filter_results)

    # ── Step 4: validate ──────────────────────────────────────────────────────
    report = _step_validate(df, filter_results, config)

    # ── Step 5: charts ────────────────────────────────────────────────────────
    chart_paths = _step_charts(df, config)

    logger.info("[bold blue]═══ Pipeline Complete ═══[/bold blue]")
    return {
        "fields": fields,
        "filter_results": filter_results,
        "dataframe": df,
        "validation_report": report,
        "chart_paths": chart_paths,
    }


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------
def _step_generate_cert(cert_out_dir: Path) -> None:
    logger.info("[Step 0] Generating TLS certificate …")
    from jira_analyser.cert import generate_self_signed_cert

    generate_self_signed_cert(out_dir=cert_out_dir, overwrite=True)


def _step_load_fields(config: PipelineConfig) -> list[JiraField]:
    logger.info("[Step 1] Loading fields (type=%s) …", config.field_type)
    loader = FieldLoader()
    fields = loader.load(
        field_type=config.field_type,
        select=config.select_fields,
        exclude=config.exclude_fields,
    )
    logger.info("  → %d fields loaded", len(fields))
    return fields


def _step_fetch_issues(config: PipelineConfig) -> list[FilterResult]:
    logger.info("[Step 2] Fetching issues for %d filter(s) …", len(config.filter_ids))
    results = fetch_issues_for_filters(
        config.filter_ids,
        fields=config.fetch_fields,
    )
    total = sum(r.count for r in results)
    logger.info("  → %d issues fetched in total", total)
    return results


def _step_validate(
    df: pd.DataFrame,
    filter_results: list[FilterResult],
    config: PipelineConfig,
) -> ValidationReport | None:
    if not config.validation_specs:
        logger.info("[Step 4] No validation specs configured — skipping.")
        return None

    logger.info("[Step 4] Validating %d spec(s) …", len(config.validation_specs))
    all_issues = [issue for r in filter_results for issue in r.issues]
    validator = FieldValidator()
    report = validator.validate(all_issues, specs=config.validation_specs)
    report.print_summary()
    return report


def _step_charts(df: pd.DataFrame, config: PipelineConfig) -> list[Path]:
    if not config.charts:
        logger.info("[Step 5] No charts configured — skipping.")
        return []

    logger.info("[Step 5] Building %d chart(s) …", len(config.charts))
    out_dir = config.output_dir
    paths: list[Path] = []

    for spec_str in config.charts:
        try:
            path = _build_chart(df, spec_str, out_dir)
            paths.append(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chart [yellow]%s[/yellow] failed: %s", spec_str, exc)

    return paths


# ---------------------------------------------------------------------------
# Chart spec parser
# ---------------------------------------------------------------------------
def _build_chart(df: pd.DataFrame, spec: str, output_dir: Path | None) -> Path:
    """Parse a chart spec string and call the appropriate chart function.

    Spec format:  ``<chart_type>:<field>[:<extra_field>]``

    Examples:
        ``bar:status``
        ``stacked_bar:status:assignee``
        ``pie:priority``
        ``time_series:created``
        ``heatmap:status:assignee``
        ``scatter:story_points:time_spent``
        ``histogram:story_points``
        ``burndown``
    """
    parts = [p.strip() for p in spec.split(":")]
    chart_type = parts[0]
    kw: dict[str, Any] = {"output_dir": output_dir} if output_dir else {}

    match chart_type:
        case "bar":
            return ch.bar_chart(df, field=parts[1], **kw)
        case "stacked_bar":
            return ch.stacked_bar_chart(df, x_field=parts[1], stack_field=parts[2], **kw)
        case "pie":
            return ch.pie_chart(df, field=parts[1], **kw)
        case "time_series":
            return ch.time_series(df, date_field=parts[1], **kw)
        case "heatmap":
            return ch.heatmap(df, row_field=parts[1], col_field=parts[2], **kw)
        case "scatter":
            return ch.scatter(df, x_field=parts[1], y_field=parts[2], **kw)
        case "histogram":
            return ch.histogram(df, field=parts[1], **kw)
        case "burndown":
            return ch.burndown(df, **kw)
        case _:
            raise ValueError(f"Unknown chart type: {chart_type!r}")
