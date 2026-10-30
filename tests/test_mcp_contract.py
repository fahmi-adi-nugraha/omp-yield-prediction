from __future__ import annotations

from omp_yield import mcp_server


def test_mcp_tools_are_callable() -> None:
    for name in ("db_ping", "db_tables", "db_schema", "db_query"):
        assert callable(getattr(mcp_server, name))
