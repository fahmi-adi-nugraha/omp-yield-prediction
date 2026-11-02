"""Local MCP server exposing database and demo DB lifecycle tools."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from omp_yield.config import Settings
from omp_yield.db import Database, OmpDatabaseError
from omp_yield.demo_db import DemoDbManager
from omp_yield.sql import UnsafeQueryError

mcp = MCPServer("omp-yield")
_db: Database | None = None
_demo_db: DemoDbManager | None = None


def _database() -> Database:
    global _db
    if _db is None:
        _db = Database(Settings())
    return _db


def _demo_db_manager() -> DemoDbManager:
    global _demo_db
    if _demo_db is None:
        _demo_db = DemoDbManager()
    return _demo_db


async def _run_demo_db(operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Run a blocking demo DB operation off the MCP event loop."""

    try:
        return await asyncio.to_thread(operation)
    except Exception as exc:  # noqa: BLE001 - MCP tool boundary
        return {"ok": False, "error": str(exc)}


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


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
    )
)
async def demo_db_status() -> dict[str, Any]:
    """Return a read-only snapshot of the demo database Docker stack."""

    return await _run_demo_db(lambda: _demo_db_manager().status())


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
    )
)
async def demo_db_logs(tail: int = 100) -> dict[str, Any]:
    """Return the tail of the demo database Compose logs."""

    return await _run_demo_db(lambda: _demo_db_manager().logs(tail=tail))


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    )
)
async def demo_db_build(force: bool = False) -> dict[str, Any]:
    """Build the demo database image if it is missing or force is set."""

    return await _run_demo_db(lambda: _demo_db_manager().build(force=force))


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    )
)
async def demo_db_up(recreate: bool = False) -> dict[str, Any]:
    """Create or start the demo database container, building if needed."""

    return await _run_demo_db(lambda: _demo_db_manager().up(recreate=recreate))


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    )
)
async def demo_db_stop() -> dict[str, Any]:
    """Stop the demo database container without removing it."""

    return await _run_demo_db(lambda: _demo_db_manager().stop())


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    )
)
async def demo_db_start() -> dict[str, Any]:
    """Start an existing stopped demo database container."""

    return await _run_demo_db(lambda: _demo_db_manager().start())


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    )
)
async def demo_db_restart() -> dict[str, Any]:
    """Restart an existing demo database container."""

    return await _run_demo_db(lambda: _demo_db_manager().restart())


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=True,
        idempotent_hint=True,
    )
)
async def demo_db_down(remove_volumes: bool = False) -> dict[str, Any]:
    """Remove the demo database stack, optionally deleting its volume."""

    return await _run_demo_db(
        lambda: _demo_db_manager().down(remove_volumes=remove_volumes)
    )


def main() -> None:
    """Run the MCP server over stdio."""

    mcp.run()


if __name__ == "__main__":
    main()
