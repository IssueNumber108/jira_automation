"""Bulk issue fetching via Jira REST API v2 ``/search`` endpoint.

Supports multiple filter IDs in one call, auto-paginates, and returns a
``FilterResult`` per filter.

Usage::

    from jira_analyser.filters.fetcher import fetch_issues_for_filters

    results = fetch_issues_for_filters(
        filter_ids=["12345", "67890"],
        fields=["summary", "status", "assignee", "customfield_10016"],
    )
    for r in results:
        print(r.filter_name, r.count)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jira_analyser.client import JiraClient
from jira_analyser.utils.logging import get_logger
from jira_analyser.utils.models import FilterResult, JiraIssue

logger = get_logger(__name__)

_SEARCH_PATH = "/rest/api/2/search"
_FILTER_PATH = "/rest/api/2/filter/{filter_id}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def fetch_issues_for_filters(
    filter_ids: list[str],
    *,
    fields: list[str] | None = None,
    expand: list[str] | None = None,
    max_results_per_page: int = 100,
) -> list[FilterResult]:
    """Fetch all issues for each filter ID.

    Args:
        filter_ids:           One or more Jira saved-filter IDs.
        fields:               Field IDs to include per issue (``None`` = all).
        expand:               Optional ``expand`` values forwarded to the API.
        max_results_per_page: Page size (1–1000).

    Returns:
        List of :class:`FilterResult`, one per filter ID, preserving order.
    """
    with JiraClient() as client:
        return [
            _fetch_single_filter(
                client,
                filter_id=fid,
                fields=fields,
                expand=expand,
                max_results_per_page=max_results_per_page,
            )
            for fid in filter_ids
        ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _resolve_filter_jql(client: JiraClient, filter_id: str) -> tuple[str, str | None]:
    """Return (jql, filter_name) for the given filter ID."""
    data: dict[str, Any] = client.get(_FILTER_PATH.format(filter_id=filter_id))
    return data["jql"], data.get("name")


def _fetch_single_filter(
    client: JiraClient,
    *,
    filter_id: str,
    fields: list[str] | None,
    expand: list[str] | None,
    max_results_per_page: int,
) -> FilterResult:
    jql, filter_name = _resolve_filter_jql(client, filter_id)
    logger.info(
        "Fetching filter [bold]%s[/bold] (%s) — JQL: %s",
        filter_id,
        filter_name or "unnamed",
        jql,
    )

    issues: list[JiraIssue] = []
    start_at = 0

    while True:
        payload = _build_search_payload(
            jql=jql,
            start_at=start_at,
            max_results=max_results_per_page,
            fields=fields,
            expand=expand,
        )
        page = client.post(_SEARCH_PATH, json=payload)
        raw_issues: list[dict[str, Any]] = page.get("issues", [])
        issues.extend(JiraIssue.from_raw(raw) for raw in raw_issues)

        total: int = page.get("total", 0)
        start_at += len(raw_issues)

        logger.debug("  … fetched %d / %d", start_at, total)

        if start_at >= total or not raw_issues:
            break

    logger.info(
        "Filter %s → [green]%d issues[/green]", filter_id, len(issues)
    )
    return FilterResult(filter_id=filter_id, filter_name=filter_name, issues=issues)


def _build_search_payload(
    *,
    jql: str,
    start_at: int,
    max_results: int,
    fields: list[str] | None,
    expand: list[str] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "jql": jql,
        "startAt": start_at,
        "maxResults": max_results,
    }
    if fields is not None:
        payload["fields"] = fields
    if expand:
        payload["expand"] = expand
    return payload
