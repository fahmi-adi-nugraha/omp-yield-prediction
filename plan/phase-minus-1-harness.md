# Phase -1 — Agent, CLI, and MCP Harness

Status: **complete**

## Overview

Create the reusable development harness before touching the data pipeline:
Python project scaffolding, read-only database CLI, local MCP tools, a dedicated
data-science agent, a read-only reviewer subagent, and reusable skills.

## Goals and deliverables

- `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `.env.example`.
- `src/omp_yield/` package with configuration, DB access, SQL guard, CLI, and
  MCP server.
- `omp-yield` CLI with `db ping`, `db tables`, `db schema`, `db query`, `info`.
- Local `omp-yield-mcp` server exposing `db_ping`, `db_tables`, `db_schema`,
  `db_query`.
- `.opencode/agents/data-science.md` — primary data-science build agent.
- `.opencode/agents/ds-reviewer.md` — read-only review subagent.
- Skills: `omp-db-access`, `omp-data-profiling`.
- Tests for SQL safety, config, CLI, MCP contract, and optional live DB access.

## Technical details

- Python 3.12, managed with `uv`.
- `connectorx` reads SQL Server into Polars; `pydantic-settings` loads
  `OMP_*` environment variables.
- `src/omp_yield/sql.py` permits one `SELECT`/`WITH` statement and rejects DML,
  DDL, `EXEC`, `INTO`, `OPENROWSET`, and multiple statements.
- `src/omp_yield/mcp_server.py` uses the MCP 2.x `MCPServer` API.
- Credentials resolve in this order: `OMP_ENV_FILE`, project `.env`,
  `~/.config/omp-yield/env`, `docker-build/.env` (local fallback only).
- The DS agent is a primary build agent; `ds-reviewer` is a read-only subagent.

## Locations

- `src/omp_yield/config.py`, `db.py`, `sql.py`, `cli.py`, `mcp_server.py`
- `tests/`
- `.opencode/agents/`, `.opencode/skills/`
- `opencode.jsonc`
- `docs/phase-minus-1-harness/README.md`

## Verification

```bash
uv run omp-yield --version
uv run omp-yield db ping
uv run omp-yield db schema --table OILPALM
uv run pytest
uv run ruff check .
uv run mypy src tests
opencode mcp list
```

The local MCP server must connect and expose the four read-only DB tools.

## Next

Phase 0 — create the least-privilege database account.
