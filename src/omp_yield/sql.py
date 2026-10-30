"""Read-only SQL validation used by the CLI and MCP tools."""

from __future__ import annotations

import re

_ALLOWED_FIRST_KEYWORD = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_FORBIDDEN = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|"
    r"EXEC|EXECUTE|GRANT|REVOKE|DENY|BACKUP|RESTORE|DBCC|"
    r"SHUTDOWN|KILL|OPENROWSET|OPENQUERY|OPENDATASOURCE|"
    r"XP_[A-Z0-9_]+|SP_[A-Z0-9_]+|INTO"
    r")\b",
    re.IGNORECASE,
)


class UnsafeQueryError(ValueError):
    """Raised when a query is not a single read-only statement."""


def strip_sql_comments(sql: str) -> str:
    """Remove SQL comments before validation."""

    without_blocks = _BLOCK_COMMENT.sub(" ", sql)
    return _LINE_COMMENT.sub(" ", without_blocks)


def validate_read_only(sql: str) -> str:
    """Validate and normalize a single read-only SQL statement.

    This is defence in depth. The database account used by the pipeline should
    also be read-only.
    """

    normalized = strip_sql_comments(sql).strip()
    if not normalized:
        raise UnsafeQueryError("Query is empty.")

    without_trailing = normalized.rstrip(";").strip()
    if ";" in without_trailing:
        raise UnsafeQueryError("Only a single SQL statement is allowed.")

    if not _ALLOWED_FIRST_KEYWORD.match(without_trailing):
        raise UnsafeQueryError("Only SELECT and WITH queries are allowed.")

    match = _FORBIDDEN.search(without_trailing)
    if match:
        raise UnsafeQueryError(f"Forbidden SQL keyword: {match.group(0).upper()}.")

    return without_trailing
