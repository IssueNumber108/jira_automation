"""Jira field discovery and loading.

Fetches all available fields from the Jira instance and lets callers:

- Load *all* fields (standard + custom)
- Load only *standard* or only *custom* fields
- Apply an **exclusion** list (remove known-noisy fields)
- Apply a **selection** list (keep only the fields you care about)

Usage::

    from jira_analyser.fields.loader import FieldLoader

    loader = FieldLoader()

    # All fields, exclude a few
    fields = loader.load(exclude=["comment", "worklog", "attachment"])

    # Only custom fields, keep a specific subset
    fields = loader.load(
        field_type="custom",
        select=["customfield_10016", "customfield_10020"],
    )
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from jira_analyser.client import JiraClient
from jira_analyser.utils.logging import get_logger
from jira_analyser.utils.models import JiraField

logger = get_logger(__name__)

_FIELDS_PATH = "/rest/api/2/field"

FieldType = Literal["all", "standard", "custom"]


class FieldLoader:
    """Discover and filter Jira fields from the REST API.

    Instantiating this class does **not** make any network calls; call
    :meth:`load` to fetch and filter.
    """

    def load(
        self,
        *,
        field_type: FieldType = "all",
        select: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> list[JiraField]:
        """Fetch and filter Jira fields.

        Args:
            field_type: Which field category to return:
                        ``"all"`` (default), ``"standard"``, or ``"custom"``.
            select:     Whitelist — keep only these field IDs/names.
                        Takes precedence over ``exclude`` when both given.
            exclude:    Blacklist — drop these field IDs/names.

        Returns:
            Ordered list of :class:`~jira_analyser.utils.models.JiraField`.
        """
        with JiraClient() as client:
            raw_fields: list[dict] = client.get(_FIELDS_PATH)

        all_fields = [_parse_field(f) for f in raw_fields]
        logger.info("Discovered %d fields in total", len(all_fields))

        filtered = _apply_type_filter(all_fields, field_type)
        logger.info("After type filter (%s): %d fields", field_type, len(filtered))

        if select:
            filtered = _apply_selection(filtered, select)
            logger.info("After selection (%d entries): %d fields", len(select), len(filtered))
        elif exclude:
            filtered = _apply_exclusion(filtered, exclude)
            logger.info("After exclusion (%d entries): %d fields", len(exclude), len(filtered))

        return filtered

    def load_standard(self, **kwargs: object) -> list[JiraField]:
        """Convenience wrapper — loads standard (non-custom) fields only."""
        return self.load(field_type="standard", **kwargs)  # type: ignore[arg-type]

    def load_custom(self, **kwargs: object) -> list[JiraField]:
        """Convenience wrapper — loads custom fields only."""
        return self.load(field_type="custom", **kwargs)  # type: ignore[arg-type]

    def field_map(self, fields: list[JiraField]) -> dict[str, JiraField]:
        """Return a dict keyed by field ID for O(1) lookups."""
        return {f.id: f for f in fields}

    def name_map(self, fields: list[JiraField]) -> dict[str, JiraField]:
        """Return a dict keyed by (lowercased) field name."""
        return {f.name.lower(): f for f in fields}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _parse_field(raw: dict) -> JiraField:
    schema = raw.get("schema", {})
    return JiraField(
        id=raw["id"],
        name=raw.get("name", raw["id"]),
        custom=raw.get("custom", False),
        schema_type=schema.get("type"),
        navigable=raw.get("navigable", False),
        searchable=raw.get("searchable", False),
        orderable=raw.get("orderable", False),
    )


def _apply_type_filter(fields: list[JiraField], field_type: FieldType) -> list[JiraField]:
    match field_type:
        case "standard":
            return [f for f in fields if not f.custom]
        case "custom":
            return [f for f in fields if f.custom]
        case _:
            return fields


def _normalise(value: str) -> str:
    return value.strip().lower()


def _apply_selection(fields: list[JiraField], select: list[str]) -> list[JiraField]:
    normalised = {_normalise(s) for s in select}
    return [f for f in fields if _normalise(f.id) in normalised or _normalise(f.name) in normalised]


def _apply_exclusion(fields: list[JiraField], exclude: list[str]) -> list[JiraField]:
    normalised = {_normalise(e) for e in exclude}
    return [
        f for f in fields if _normalise(f.id) not in normalised and _normalise(f.name) not in normalised
    ]
