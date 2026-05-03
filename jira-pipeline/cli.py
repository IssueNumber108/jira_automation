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
        "--dry-run",
        action="store_true",
        help="Print the resolved execution plan and exit without fetching or writing anything.",
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

    CLI --filters override the defaults.  Unrecognised IDs receive a
    minimal fallback: no issue-type filter (keep whatever the Jira JQL
    returns) and the same chart set as the first configured filter.
    """
    # Default chart list comes from the first entry in DEFAULT_FILTERS so it
    # stays in sync with settings; only fall back to an empty list if there
    # are no configured filters at all.
    _first_cfg   = next(iter(settings.DEFAULT_FILTERS.values()), {})
    _default_charts = _first_cfg.get("charts", [])

    if args.filters:
        result = {}
        for fid in args.filters:
            if fid in settings.DEFAULT_FILTERS:
                result[fid] = settings.DEFAULT_FILTERS[fid]
            else:
                # Unknown filter: trust the JQL (no extra issue-type filter)
                result[fid] = {
                    "title": f"Filter {fid}",
                    "issue_types": [],          # keep all types the JQL returns
                    "charts": list(_default_charts),
                }
        return result

    return dict(settings.DEFAULT_FILTERS)


def _resolve_local_path(fid: str, fcfg: dict) -> Path | None:
    """
    Find the local data file for a filter, checking (in order):
      1. 'local_file' key inside the filter config
      2. settings.LOCAL_FILES dict (legacy)
      3. Auto-discovery: data/filter_<id>.xlsx then .csv
    """
    # 1. Per-filter config key
    if "local_file" in fcfg:
        return Path(fcfg["local_file"])

    # 2. Legacy standalone LOCAL_FILES dict
    legacy = getattr(settings, "LOCAL_FILES", {})
    if fid in legacy:
        return legacy[fid]

    # 3. Auto-discover
    for ext in ("xlsx", "csv"):
        candidate = settings.DATA_DIR / f"filter_{fid}.{ext}"
        if candidate.exists():
            return candidate

    return None


def dry_run(args: argparse.Namespace) -> None:
    """Print the execution plan without touching Jira or the filesystem."""
    filters = resolve_filters(args)
    fmt     = args.format or settings.EXPORT_FORMAT
    use_local = args.local or args.report_only

    print("\n=== DRY RUN – execution plan ===\n")
    print(f"  Mode       : {'local files' if use_local else 'Jira API'}")
    print(f"  Export fmt : {fmt}")
    print(f"  Filters    : {len(filters)}\n")

    for i, (fid, fcfg) in enumerate(filters.items(), 1):
        title       = fcfg.get("title", f"Filter {fid}")
        issue_types = fcfg.get("issue_types") or ["<all>"]
        charts      = fcfg.get("charts", [])
        print(f"  [{i}] Filter ID : {fid}")
        print(f"       Title     : {title}")
        print(f"       Types     : {', '.join(issue_types)}")
        print(f"       Charts    : {', '.join(charts)}")

        if use_local:
            local_path = _resolve_local_path(fid, fcfg)
            print(f"       Source    : {local_path or '** NOT FOUND **'}")
        else:
            api = f"{settings.JIRA_URL.rstrip('/')}{settings.JIRA_API_PATH}"
            print(f"       Jira call : GET {api}/filter/{fid}  →  search")

        data_out   = settings.DATA_DIR   / f"filter_{fid}.{fmt}"
        report_out = settings.REPORTS_DIR / f"report_{fid}.pdf"
        print(f"       → Data     : {data_out}")
        print(f"       → Report   : {report_out}")
        print()

    # Warn about missing env vars for live mode
    if not use_local:
        missing = [v for v in ("JIRA_URL", "JIRA_TOKEN") if not getattr(settings, v, "")]
        if missing:
            print(f"  ⚠  Missing env vars: {', '.join(missing)}")
            print("     Set them before running without --local.\n")
        else:
            print("  ✓  JIRA_URL and JIRA_TOKEN are configured.\n")

    print("=== end of plan ===\n")


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
        title       = fcfg.get("title", f"Filter {fid}")
        issue_types = fcfg.get("issue_types") or None   # None = keep all types
        chart_keys  = fcfg.get("charts")

        logger.info("=" * 60)
        logger.info("Processing filter %s  –  %s", fid, title)
        logger.info("=" * 60)

        # ---- Ingestion --------------------------------------------------
        if use_local:
            local_path = _resolve_local_path(fid, fcfg)
            if local_path is None:
                logger.error(
                    "No local file configured or found for filter %s – skipping.", fid
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

    if args.dry_run:
        dry_run(args)
    else:
        run_pipeline(args)


if __name__ == "__main__":
    main()
