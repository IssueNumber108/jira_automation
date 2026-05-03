"""
Jira REST API v2 client.

Fetches issues for a given filter ID with automatic pagination.
Authentication via Bearer token; optional client certificate (.pem).
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from config import settings

logger = logging.getLogger(__name__)


class JiraClientError(Exception):
    """Raised when a Jira API call fails."""


class JiraClient:
    """Thin wrapper around Jira REST API v2."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        cert_path: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.JIRA_URL).rstrip("/")
        self.token = token or settings.JIRA_TOKEN
        self.cert_path = cert_path or settings.JIRA_CERT or None
        self.api = f"{self.base_url}{settings.JIRA_API_PATH}"

        if not self.base_url:
            raise JiraClientError("JIRA_URL is not configured.")
        if not self.token:
            raise JiraClientError("JIRA_TOKEN is not configured.")

        self._session = self._build_session()

    # ------------------------------------------------------------------
    # Session setup
    # ------------------------------------------------------------------
    def _build_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }
        )
        if self.cert_path:
            s.cert = self.cert_path
        s.verify = settings.JIRA_VERIFY_SSL
        return s

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def fetch_filter_issues(
        self,
        filter_id: str,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return all issues matching a saved Jira filter.

        Paginates automatically until all results are fetched.
        """
        max_results = max_results or settings.JIRA_MAX_RESULTS
        jql = self._get_filter_jql(filter_id)
        logger.info("Filter %s  →  JQL: %s", filter_id, jql)
        return self._search(jql, max_results)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _get_filter_jql(self, filter_id: str) -> str:
        """Retrieve the JQL string stored in a Jira filter."""
        url = f"{self.api}/filter/{filter_id}"
        resp = self._session.get(url, timeout=30)
        if resp.status_code != 200:
            raise JiraClientError(
                f"Failed to fetch filter {filter_id}: "
                f"{resp.status_code} {resp.text[:300]}"
            )
        data = resp.json()
        jql = data.get("jql", "")
        if not jql:
            raise JiraClientError(f"Filter {filter_id} has no JQL.")
        return jql

    def _search(
        self,
        jql: str,
        max_results: int,
    ) -> list[dict[str, Any]]:
        """Execute a JQL search with pagination."""
        url = f"{self.api}/search"
        all_issues: list[dict[str, Any]] = []
        start_at = 0

        # Only request the fields we actually need
        field_keys = [
            v.split(".")[1] if v.startswith("fields.") else v
            for v in settings.JIRA_FIELDS.values()
            if v != "key"
        ]
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_fields: list[str] = []
        for f in field_keys:
            root = f.split(".")[0]
            if root not in seen:
                seen.add(root)
                unique_fields.append(root)

        while True:
            params = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": max_results,
                "fields": ",".join(unique_fields),
            }
            resp = self._session.get(url, params=params, timeout=60)
            if resp.status_code != 200:
                raise JiraClientError(
                    f"Search failed: {resp.status_code} {resp.text[:300]}"
                )
            body = resp.json()
            issues = body.get("issues", [])
            all_issues.extend(issues)

            total = body.get("total", 0)
            start_at += len(issues)
            logger.info(
                "  fetched %d / %d issues",
                start_at,
                total,
            )
            if start_at >= total or not issues:
                break

        return all_issues
