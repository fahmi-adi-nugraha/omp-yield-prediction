"""Thin, read-only database access layer backed by ConnectorX and Polars."""

from __future__ import annotations

import json
from typing import Any

import connectorx as cx
import polars as pl

from omp_yield.config import Settings
from omp_yield.sql import validate_read_only


class OmpDatabaseError(RuntimeError):
    """Raised when the OMP database cannot be reached or queried."""


class Database:
    """Read-only query client for the OMP SQL Server database."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def _read(self, sql: str) -> pl.DataFrame:
        validated = validate_read_only(sql)
        try:
            frame = cx.read_sql(
                self.settings.mssql_url,
                validated,
                return_type="polars",
            )
        except Exception as exc:  # noqa: BLE001 - surface driver errors with context
            raise OmpDatabaseError(f"Database query failed: {exc}") from exc
        if not isinstance(frame, pl.DataFrame):
            frame = pl.DataFrame(frame)
        return frame

    def ping(self) -> pl.DataFrame:
        """Return server/database identity and the OILPALM row count."""

        return self._read(
            """
            SELECT
                DB_NAME() AS database_name,
                SUSER_SNAME() AS login_name,
                @@VERSION AS server_version,
                (SELECT COUNT(*) FROM dbo.OILPALM) AS oilpalm_rows
            """
        )

    def tables(self) -> pl.DataFrame:
        """List user tables in the current database."""

        return self._read(
            """
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
            """
        )

    def schema(self, table: str | None = None) -> pl.DataFrame:
        """Return column metadata, optionally filtered to one table."""

        base = """
            SELECT
                TABLE_SCHEMA,
                TABLE_NAME,
                ORDINAL_POSITION,
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
        """
        if table:
            safe_table = table.replace("'", "''")
            sql = (
                base
                + f" WHERE TABLE_NAME = '{safe_table}'"
                + " ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION"
            )
        else:
            sql = base + " ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION"
        return self._read(sql)

    def query(self, sql: str, limit: int | None = None) -> pl.DataFrame:
        """Run a read-only query and truncate the result client-side."""

        max_rows = limit or self.settings.query_row_limit
        max_rows = max(1, min(max_rows, self.settings.query_row_limit))
        frame = self._read(sql)
        return frame.head(max_rows)

    def query_payload(self, sql: str, limit: int | None = None) -> dict[str, Any]:
        """Run a query and return a JSON-serializable payload for MCP tools."""

        max_rows = limit or self.settings.query_row_limit
        max_rows = max(1, min(max_rows, self.settings.query_row_limit))
        frame = self._read(sql)
        total_rows = frame.height
        limited = frame.head(max_rows)
        rows = json.loads(limited.write_json())
        return {
            "columns": limited.columns,
            "rows": rows,
            "row_count": limited.height,
            "total_rows_fetched": total_rows,
            "truncated": total_rows > max_rows,
        }
