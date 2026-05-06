"""Authenticated HTTP client for the Jira REST API v2."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from jira_analyser.utils.logging import get_logger

logger = get_logger(__name__)

_RETRYABLE = (httpx.TransportError, httpx.TimeoutException)
_DEFAULT_MAX_RETRIES = 3


def _get_settings() -> Any:
    from jira_analyser.config import settings
    return settings


def _build_client() -> httpx.Client:
    s = _get_settings()
    return httpx.Client(
        base_url=s.jira_base_url,
        auth=httpx.BasicAuth(username=s.jira_email, password=s.jira_api_token),
        verify=str(s.jira_cert_path),
        timeout=s.jira_request_timeout,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Atlassian-Token": "no-check",
        },
    )


class JiraClient:
    """Context-manager-friendly Jira REST API v2 client."""

    def __init__(self) -> None:
        self._client = _build_client()
        self._max_retries: int = _get_settings().jira_max_retries

    def __enter__(self) -> "JiraClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """HTTP GET with retry."""
        logger.debug("GET %s  params=%s", path, params)

        @retry(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(self._max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        def _do() -> Any:
            response = self._client.get(path, params=params)
            _raise_for_status(response)
            return response.json()

        return _do()

    def post(self, path: str, *, json: dict[str, Any]) -> Any:
        """HTTP POST with retry."""
        logger.debug("POST %s", path)

        @retry(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(self._max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        def _do() -> Any:
            response = self._client.post(path, json=json)
            _raise_for_status(response)
            return response.json()

        return _do()


class JiraApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"Jira API error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    try:
        body = response.json()
        messages = body.get("errorMessages") or body.get("errors") or [response.text]
        detail = "; ".join(str(m) for m in (messages if isinstance(messages, list) else [messages]))
    except Exception:
        detail = response.text
    raise JiraApiError(response.status_code, detail)
