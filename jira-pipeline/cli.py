#!/usr/bin/env python3
"""
CLI entry point for the Jira data pipeline.

Usage examples:
    uv run python cli.py                          # full pipeline (fetch + export + report)
    uv run python cli.py --filters 12345 67890    # specific filters
    uv run python cli.py --export-raw             # raw export only, no PDF
    uv run python cli.py --report-only --local    # PDF from local files
    uv run python cli.py --format csv             # override export format
"""

from __future__ import annotations
from src.reporting.pdf_report import generate_pdf_report
from src.processing.exporter import export_raw
from src.processing.transforms import preprocess
from src.ingestion.file_loader import load_local_file, LoaderError
from src.ingestion.parser import issues_to_dataframe
from src.ingestion.jira_client import JiraClient, JiraClientError
from config import settings

import argparse
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so imports resolve when invoked directly
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


logger = logging.getLogger("jira_pipeline")


# -----------------------------------------------------------------------
# Argument parser
# -----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jira-pipeline",
        description="Jira data pipeline – fetch, analyse, and report.",
    )
    p.add_argument(
        "--filters",
        nargs="+",
        default=None,
        help="Jira filter IDs to process (default: from config).",
    )
    p.add_argument(
        "--export-raw",
        action="store_true",
        help="Export raw data only; skip PDF report generation.",
    )
    p.add_argument(
        "--report-only",
        action="store_true",
        help="Generate PDF reports from existing local data (implies --local).",
    )
    p.add_argument(
        "--local",
        action="store_true",
        help="Load data from local files instead of fetching from Jira.",
    )
    p.add_argument(
        "--format",
        choices=["csv", "xlsx"],
        default=None,
        help=f"Export format (default: {settings.EXPORT_FORMAT}).",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return p


# -----------------------------------------------------------------------
# Pipeline orchestration
# -----------------------------------------------------------------------


def resolve_filters(args: argparse.Namespace) -> dict[str, dict]:
    """
    Return a dict of {filter_id: config} to process.

    CLI --filters override the defaults; unrecognised IDs get a
    sensible fallback config.
    """
    if args.filters:
        result = {}
        for fid in args.filters:
            if fid in settings.DEFAULT_FILTERS:
                result[fid] = settings.DEFAULT_FILTERS[fid]
            else:
                result[fid] = {
                    "title": f"Filter {fid}",
                    "issue_types": ["Change Request", "Problem Report"],
                    "charts": list(
                        settings.DEFAULT_FILTERS.get(
                            next(iter(settings.DEFAULT_FILTERS), ""),
                            {},
                        ).get(
                            "charts",
                            [
                                "time_deviation",
                                "missing_due_dates",
                                "status_distribution",
                                "aging",
                            ],
                        )
                    ),
                }
        return result

    return dict(settings.DEFAULT_FILTERS)


def run_pipeline(args: argparse.Namespace) -> None:
    """Execute the pipeline for every resolved filter."""
    filters = resolve_filters(args)
    fmt = args.format or settings.EXPORT_FORMAT
    use_local = args.local or args.report_only

    if not filters:
        logger.error(
            "No filter IDs to process. Pass --filters or configure DEFAULT_FILTERS."
        )
        sys.exit(1)

    jira: JiraClient | None = None
    if not use_local:
        try:
            jira = JiraClient()
        except JiraClientError as exc:
            logger.error("Cannot initialise Jira client: %s", exc)
            sys.exit(1)

    for fid, fcfg in filters.items():
        title = fcfg.get("title", f"Filter {fid}")
        issue_types = fcfg.get("issue_types")
        chart_keys = fcfg.get("charts")

        logger.info("=" * 60)
        logger.info("Processing filter %s  –  %s", fid, title)
        logger.info("=" * 60)

        # ---- Ingestion --------------------------------------------------
        if use_local:
            local_path = settings.LOCAL_FILES.get(fid)
            if local_path is None:
                # Attempt to find an auto-exported file
                for ext in ("xlsx", "csv"):
                    candidate = settings.DATA_DIR / f"filter_{fid}.{ext}"
                    if candidate.exists():
                        local_path = candidate
                        break
            if local_path is None:
                logger.error(
                    "No local file configured or found for filter %s – skipping.",
                    fid,
                )
                continue
            try:
                df = load_local_file(local_path)
            except LoaderError as exc:
                logger.error("Failed to load local file: %s", exc)
                continue
        else:
            assert jira is not None
            try:
                raw_issues = jira.fetch_filter_issues(fid)
            except JiraClientError as exc:
                logger.error("Jira fetch failed for filter %s: %s", fid, exc)
                continue
            df = issues_to_dataframe(raw_issues)

        # ---- Processing -------------------------------------------------
        df = preprocess(df, issue_types=issue_types)

        if df.empty:
            logger.warning(
                "Filter %s returned 0 rows after preprocessing – skipping.", fid
            )
            continue

        # ---- Export raw data --------------------------------------------
        if not args.report_only:
            export_raw(df, filter_id=fid, fmt=fmt)

        # ---- PDF report -------------------------------------------------
        if not args.export_raw:
            generate_pdf_report(
                df,
                filter_id=fid,
                title=title,
                chart_keys=chart_keys,
            )

    logger.info("Pipeline complete.")


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    run_pipeline(args)


if __name__ == "__main__":
    main()
