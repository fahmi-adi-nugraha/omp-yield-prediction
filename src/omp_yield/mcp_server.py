"""Local MCP server exposing the Phase -1 read-only database tools."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer

from omp_yield.config import Settings
from omp_yield.db import Database, OmpDatabaseError
from omp_yield.sql import UnsafeQueryError

mcp = MCPServer("omp-yield")
_db: Database | None = None


def _database() -> Database:
    global _db
    if _db is None:
        _db = Database(Settings())
    return _db


@mcp.tool()
def db_ping() -> dict[str, Any]:
    """Check the OMP database connection and return server identity."""

    try:
        frame = _database().ping()
        return {"ok": True, "rows": json.loads(frame.write_json())}
    except (OmpDatabaseError, UnsafeQueryError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def db_tables() -> dict[str, Any]:
    """List user tables in the configured OMP database."""

    try:
        frame = _database().tables()
        return {"ok": True, "tables": json.loads(frame.write_json())}
    except (OmpDatabaseError, UnsafeQueryError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def db_schema(table: str | None = None) -> dict[str, Any]:
    """Return column metadata, optionally filtered to one table."""

    try:
        frame = _database().schema(table=table)
        return {"ok": True, "columns": json.loads(frame.write_json())}
    except (OmpDatabaseError, UnsafeQueryError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def db_query(sql: str, limit: int = 100) -> dict[str, Any]:
    """Run one read-only SELECT/WITH query with a client-side row limit."""

    try:
        payload = _database().query_payload(sql, limit=limit)
        return {"ok": True, **payload}
    except (OmpDatabaseError, UnsafeQueryError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def main() -> None:
    """Run the MCP server over stdio."""

    mcp.run()


if __name__ == "__main__":
    main()
