# Phase -1 — Agent and Tooling Harness

Status: **complete**

## What was created

### Project scaffold

- `pyproject.toml`, `uv.lock`, `.python-version` (Python 3.12)
- `src/omp_yield/` package with:
  - `config.py` — environment settings and MSSQL connection URL
  - `db.py` — read-only ConnectorX/Polars client
  - `sql.py` — single-statement read-only SQL guard
  - `cli.py` — `omp-yield` CLI
  - `mcp_server.py` — local MCP server
- `tests/` — SQL guard, settings, and CLI tests
- `.env.example`, `.gitignore`, `README.md`

### Agent and skills

- `.opencode/agents/data-science.md` — primary DS build agent
- `.opencode/agents/ds-reviewer.md` — read-only review subagent
- `.opencode/skills/omp-db-access/SKILL.md` — schema map, joins, safety
- `.opencode/skills/omp-data-profiling/SKILL.md` — cleaning/leakage/lever audit
- `opencode.jsonc` — default agent and `omp-yield` MCP server

### Read-only database tools

CLI:

```bash
uv run omp-yield db ping
uv run omp-yield db tables
uv run omp-yield db schema --table OILPALM
uv run omp-yield db query "SELECT TOP 5 ... FROM OILPALM"
```

MCP tools:

- `db_ping`
- `db_tables`
- `db_schema`
- `db_query`

## Verification performed

### Connectivity

```text
database_name: omp_as_demo
login_name: sa
server_version: Microsoft SQL Server 2025 (RTM-CU6) 17.0.4055.5
oilpalm_rows: 2909
```

`sa` is used only for local bootstrap. Phase 0 creates `omp_ds_readonly`.

### Read-only guard

```text
$ uv run omp-yield db query "DELETE FROM OILPALM"
Error: Only SELECT and WITH queries are allowed.
exit=1
```

### Tests

```text
$ uv run pytest
17 passed, 2 skipped

$ OMP_RUN_INTEGRATION=1 uv run pytest tests/test_db_integration.py
2 passed

$ uv run ruff check .
All checks passed!

$ uv run mypy src tests
Success: no issues found in 11 source files
```

### MCP server

The local MCP server was started over stdio and queried with an MCP client:

```text
tools: ['db_ping', 'db_tables', 'db_schema', 'db_query']
db_ping: ok=True, oilpalm_rows=2909
db_schema('OILPALM'): 207 columns
```

OpenCode connects to it successfully:

```text
$ opencode mcp list
✓ omp-yield  connected
```

## Known Phase -1 limitations

- The client-side row limit fetches the result and truncates it in Polars. This
  is acceptable for the current tables; a server-side or cursor-based limit can
  be added later for large extracts.
- No retry/backoff yet. DB connection errors are surfaced with context.
- The MCP server has no authentication because it is a local stdio server. The
  DB account itself must be read-only.
- Local development falls back to `~/.config/omp-yield/env`, then
  `docker-build/.env` when no project `.env` exists. Production should use
  environment variables or a managed secret store.
- `sa` was the local account during Phase -1; Phase 0 created
  `omp_ds_readonly` and the CLI now uses it.

## Next

Phase 0, Phase 1, Phase 2, and Phase 3 are complete. See
`../../reports/00_access.md`, `../phase-1-inventory/README.md`,
`../phase-2-extraction/README.md`, `../phase-3-cleaning/README.md`, and
`../../reports/03_cleaning_report.html`.

Phase 4:

1. Use the approved `config/features.yaml` and `config/management_levers.yaml`.
2. Build cutoff-safe derived features and the final modeling table.
3. Run feature regression tests and leakage checks.
4. Proceed to time-aware model training and validation.
