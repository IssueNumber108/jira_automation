"""Shared domain models and type aliases used across the package."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
IssueKey = str
FieldId = str
RawIssue = dict[str, Any]
RawFields = dict[str, Any]


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------
class JiraField(BaseModel):
    """Represents a single Jira field descriptor."""

    id: FieldId
    name: str
    custom: bool
    schema_type: str | None = Field(default=None, alias="clauseNames")
    navigable: bool = False
    searchable: bool = False
    orderable: bool = False

    model_config = {"populate_by_name": True}


class JiraIssue(BaseModel):
    """Lightweight wrapper around a raw Jira issue dict."""

    key: IssueKey
    id: str
    fields: RawFields

    @classmethod
    def from_raw(cls, raw: RawIssue) -> "JiraIssue":
        return cls(key=raw["key"], id=raw["id"], fields=raw.get("fields", {}))

    def field_value(self, field_id: FieldId) -> Any:
        return self.fields.get(field_id)


class FilterResult(BaseModel):
    """Issues fetched for a single Jira filter."""

    filter_id: str
    filter_name: str | None = None
    issues: list[JiraIssue] = Field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.issues)
