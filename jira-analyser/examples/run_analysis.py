#!/usr/bin/env python
"""Example: run a full analysis pipeline from Python.

Copy this file, adjust the config, and run::

    uv run python examples/run_analysis.py
"""

from __future__ import annotations

from pathlib import Path

from jira_analyser.pipeline.runner import PipelineConfig, run_pipeline
from jira_analyser.validation.validator import ValidationSpec


def main() -> None:
    config = PipelineConfig(
        # ── Replace these with your real filter IDs ──
        filter_ids=["12345", "67890"],

        # Load all field types, but drop noisy ones
        field_type="all",
        exclude_fields=["comment", "worklog", "attachment", "watches"],

        # Only request these fields per issue (faster fetch)
        fetch_fields=[
            "summary",
            "status",
            "priority",
            "assignee",
            "created",
            "resolutiondate",
            "customfield_10016",  # Story Points — adjust to your instance
        ],

        # Validate that status and priority have expected values
        validation_specs=[
            ValidationSpec(
                field_id="status",
                allowed_values=["To Do", "In Progress", "In Review", "Done"],
            ),
            ValidationSpec(
                field_id="priority",
                allowed_values=["Highest", "High", "Medium", "Low", "Lowest"],
            ),
        ],

        # Charts to produce
        charts=[
            "bar:status",
            "bar:priority",
            "stacked_bar:status:priority",
            "pie:priority",
            "time_series:created",
            "burndown",
        ],

        output_dir=Path("outputs"),
    )

    results = run_pipeline(config)

    print(f"\nFetched {sum(r.count for r in results['filter_results'])} issues")
    print(f"DataFrame shape: {results['dataframe'].shape}")
    print(f"Charts: {[str(p) for p in results['chart_paths']]}")


if __name__ == "__main__":
    main()
