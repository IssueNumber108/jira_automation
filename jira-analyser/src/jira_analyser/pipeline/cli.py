"""Command-line interface for the Jira Analyser pipeline.

Entry-point registered as ``jira-analyser`` in pyproject.toml.

Examples
--------
Fetch two filters and build bar + burndown charts::

    jira-analyser run \\
        --filter 12345 --filter 67890 \\
        --chart "bar:status" --chart burndown

Generate a certificate only::

    jira-analyser cert --out-dir certs/ --cn myorg.atlassian.net

Load and inspect fields::

    jira-analyser fields --type custom --exclude comment --exclude worklog
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from jira_analyser.cert import generate_self_signed_cert
from jira_analyser.fields import FieldLoader
from jira_analyser.pipeline.runner import PipelineConfig, run_pipeline
from jira_analyser.validation.validator import ValidationSpec

app = typer.Typer(
    name="jira-analyser",
    help="Jira issue analysis toolkit.",
    add_completion=False,
)
_console = Console()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
@app.command()
def run(
    filter_ids: Annotated[
        list[str],
        typer.Option("--filter", "-f", help="Jira filter ID (repeatable)"),
    ],
    field_type: Annotated[
        str,
        typer.Option("--field-type", help="all | standard | custom"),
    ] = "all",
    exclude_fields: Annotated[
        list[str],
        typer.Option("--exclude-field", help="Field ID/name to exclude (repeatable)"),
    ] = [],  # noqa: B006
    select_fields: Annotated[
        list[str],
        typer.Option("--select-field", help="Field ID/name to select (repeatable)"),
    ] = [],  # noqa: B006
    charts: Annotated[
        list[str],
        typer.Option(
            "--chart",
            "-c",
            help='Chart spec, e.g. "bar:status" or "burndown" (repeatable)',
        ),
    ] = [],  # noqa: B006
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Output directory for charts"),
    ] = None,
    generate_cert: Annotated[
        bool,
        typer.Option("--generate-cert/--no-generate-cert", help="Regenerate TLS cert"),
    ] = False,
) -> None:
    """Run the full analysis pipeline."""
    config = PipelineConfig(
        filter_ids=filter_ids,
        field_type=field_type,  # type: ignore[arg-type]
        exclude_fields=exclude_fields or None,
        select_fields=select_fields or None,
        charts=charts,
        output_dir=output_dir,
        generate_cert=generate_cert,
    )
    results = run_pipeline(config)
    report = results.get("validation_report")
    if report:
        _console.print("\n[bold]Validation summary:[/bold]")
        report.print_summary()

    paths = results.get("chart_paths", [])
    if paths:
        _console.print("\n[bold green]Charts written:[/bold green]")
        for p in paths:
            _console.print(f"  {p}")


@app.command()
def cert(
    out_dir: Annotated[Path, typer.Option("--out-dir", help="Output directory")] = Path("certs"),
    cn: Annotated[str, typer.Option("--cn", help="Common name")] = "localhost",
    org: Annotated[str, typer.Option("--org", help="Organisation")] = "jira-analyser",
    country: Annotated[str, typer.Option("--country", help="Two-letter country code")] = "US",
    days: Annotated[int, typer.Option("--days", help="Validity in days")] = 825,
    overwrite: Annotated[bool, typer.Option("--overwrite/--no-overwrite")] = False,
) -> None:
    """Generate a self-signed TLS certificate."""
    cert_path, key_path = generate_self_signed_cert(
        out_dir=out_dir,
        common_name=cn,
        organisation=org,
        country=country,
        validity_days=days,
        overwrite=overwrite,
    )
    _console.print(f"[green]Certificate:[/green] {cert_path}")
    _console.print(f"[green]Private key:[/green] {key_path}")


@app.command()
def fields(
    field_type: Annotated[
        str,
        typer.Option("--type", help="all | standard | custom"),
    ] = "all",
    exclude: Annotated[
        list[str],
        typer.Option("--exclude", help="Field ID/name to exclude (repeatable)"),
    ] = [],  # noqa: B006
    select: Annotated[
        list[str],
        typer.Option("--select", help="Field ID/name to select (repeatable)"),
    ] = [],  # noqa: B006
) -> None:
    """Discover and list available Jira fields."""
    loader = FieldLoader()
    result = loader.load(
        field_type=field_type,  # type: ignore[arg-type]
        exclude=exclude or None,
        select=select or None,
    )

    table = Table(title=f"Jira Fields ({field_type})", show_lines=False)
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Custom", justify="center")
    table.add_column("Type")

    for f in result:
        table.add_row(
            f.id,
            f.name,
            "[green]✓[/green]" if f.custom else "",
            f.schema_type or "—",
        )

    _console.print(table)
    _console.print(f"\nTotal: [bold]{len(result)}[/bold] fields")


if __name__ == "__main__":
    app()
